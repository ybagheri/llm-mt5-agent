"""Serve the read-only dashboard until Ctrl+C (connects, serves, disconnects)."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mt5_agent.application.account_service import AccountService  # noqa: E402
from mt5_agent.application.connection_service import (  # noqa: E402
    ConnectionService,
    RetryPolicy,
)
from mt5_agent.application.health import (  # noqa: E402
    ComponentHealth,
    HealthService,
    HealthStatus,
)
from mt5_agent.application.history_service import HistoryService  # noqa: E402
from mt5_agent.application.market_service import MarketService  # noqa: E402
from mt5_agent.application.order_service import OrderService  # noqa: E402
from mt5_agent.application.position_service import PositionService  # noqa: E402
from mt5_agent.application.strategy_service import StrategyService  # noqa: E402
from mt5_agent.config.loader import load_settings  # noqa: E402
from mt5_agent.dashboard.app import DashboardApp  # noqa: E402
from mt5_agent.dashboard.provider import DashboardStateProvider  # noqa: E402
from mt5_agent.domain.market import Timeframe  # noqa: E402
from mt5_agent.domain.memory import MemoryScope  # noqa: E402
from mt5_agent.domain.terminal import MT5Credentials  # noqa: E402
from mt5_agent.infrastructure.mt5.connection_adapter import (  # noqa: E402
    MT5ConnectionAdapter,
)
from mt5_agent.infrastructure.mt5.market_adapter import MT5MarketDataAdapter  # noqa: E402
from mt5_agent.infrastructure.mt5.trading_adapter import (  # noqa: E402
    MT5TradingDataAdapter,
)
from mt5_agent.logging_utils import configure_logging, get_logger  # noqa: E402
from mt5_agent.memory.memories import StrategyMemory, TradeMemory, WorldMemory  # noqa: E402
from mt5_agent.memory.sqlite_store import SQLiteMemoryStore  # noqa: E402
from mt5_agent.strategies.measure_move import DonchianBreakoutStrategy  # noqa: E402
from mt5_agent.strategies.null_strategy import NullStrategy  # noqa: E402


def _build_health(conn, market, store, settings) -> HealthService:  # noqa: ANN001, ANN202
    """Aggregate probes for `GET /api/health` (each best-effort, never raises)."""

    def mt5_probe() -> ComponentHealth:
        health = conn.check_health()
        if health.connected:
            return ComponentHealth("mt5", HealthStatus.HEALTHY, "terminal connected")
        return ComponentHealth("mt5", HealthStatus.UNHEALTHY, health.error or "disconnected")

    def market_probe() -> ComponentHealth:
        snapshot = market.get_snapshot(settings.mt5_default_symbol, Timeframe.M1, count=5)
        if not snapshot.candles:
            return ComponentHealth("market", HealthStatus.DEGRADED, "no candles returned")
        return ComponentHealth("market", HealthStatus.HEALTHY, "snapshot ok")

    def memory_probe() -> ComponentHealth:
        store.count(MemoryScope.SHORT_TERM)
        return ComponentHealth("memory", HealthStatus.HEALTHY, "sqlite reachable")

    def llm_probe() -> ComponentHealth:
        if settings.llm_provider == "none":
            return ComponentHealth(
                "llm", HealthStatus.DEGRADED, "not configured (HOLD fallback active)"
            )
        return ComponentHealth("llm", HealthStatus.HEALTHY, "configured (HOLD on failure)")

    def executor_probe() -> ComponentHealth:
        return ComponentHealth("executor", HealthStatus.HEALTHY, f"mode={settings.execution_mode}")

    return HealthService(
        {
            "mt5": mt5_probe,
            "market": market_probe,
            "memory": memory_probe,
            "llm": llm_probe,
            "executor": executor_probe,
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the read-only dashboard.")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(level=settings.log_level, log_format=settings.log_format)
    logger = get_logger("serve_dashboard")

    conn = MT5ConnectionAdapter()
    connection_service = ConnectionService(conn, RetryPolicy(max_attempts=2, delay_seconds=1.0))
    login_raw = os.getenv("MT5_AGENT_MT5_LOGIN") or str(settings.mt5_login or "")
    password = os.getenv("MT5_AGENT_MT5_PASSWORD", "")
    server = os.getenv("MT5_AGENT_MT5_SERVER") or str(settings.mt5_server or "")
    creds = (
        MT5Credentials(login=int(login_raw), password=password, server=server)
        if login_raw.strip() and password and server.strip()
        else None
    )
    try:
        connection_service.ensure_connected(settings.to_connection_config(), creds)
    except Exception as exc:
        logger.warning("mt5 connection failed", extra={"extra_fields": {"error": str(exc)}})
        print(json.dumps({"connected": False, "error": str(exc)}))
        return 1

    store = SQLiteMemoryStore(settings.memory_db_path)
    app: DashboardApp | None = None
    try:
        from mt5_agent import __version__  # noqa: E402

        market = MarketService(MT5MarketDataAdapter(connection=conn))
        trading = MT5TradingDataAdapter(connection=conn)
        account = AccountService(conn, trading, trading)
        provider = DashboardStateProvider(
            market=market,
            account=account,
            positions=PositionService(trading),
            orders=OrderService(trading),
            strategies=StrategyService([NullStrategy(), DonchianBreakoutStrategy()]),
            risk_config=settings.to_risk_config(),
            history=HistoryService(trading),
            trade_memory=TradeMemory(store),
            strategy_memory=StrategyMemory(store),
            world_memory=WorldMemory(store),
            llm_provider_name=settings.llm_provider,
            llm_model=settings.llm_model or "",
            version=__version__,
            trading_mode=settings.trading_mode,
        )
        health = _build_health(conn, market, store, settings)
        app = DashboardApp(
            provider,
            host=args.host or settings.dashboard_host,
            port=args.port or settings.dashboard_port,
            default_symbol=settings.mt5_default_symbol,
            refresh_s=settings.dashboard_refresh_s,
            health_provider=lambda: health.check().to_dict(),
        )
        url = app.start()
        print(f"Dashboard (read-only): {url}")
        print("Press Ctrl+C to stop.")

        stop = False

        def _stop(signum: int, frame: object) -> None:  # noqa: ANN001, ANN202
            nonlocal stop
            stop = True

        signal.signal(signal.SIGINT, _stop)
        try:
            signal.signal(signal.SIGTERM, _stop)
        except (AttributeError, ValueError, OSError):
            pass
        while not stop:
            time.sleep(0.2)
        return 0
    except Exception as exc:
        logger.warning("dashboard failed", extra={"extra_fields": {"error": str(exc)}})
        print(json.dumps({"error": str(exc)}))
        return 1
    finally:
        if app is not None:
            app.stop()
        store.close()
        connection_service.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
