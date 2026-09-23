"""Run the agent: one cycle by default, `--loop` for continuous (Ctrl+C stops)."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mt5_agent.ai.factory import provider_from_settings  # noqa: E402
from mt5_agent.ai.planner import LLMPlanner  # noqa: E402
from mt5_agent.application.account_service import AccountService  # noqa: E402
from mt5_agent.application.agent import (  # noqa: E402
    ContextBuilder,
    Observer,
    TradingAgent,
)
from mt5_agent.application.connection_service import (  # noqa: E402
    ConnectionService,
    RetryPolicy,
)
from mt5_agent.application.market_service import MarketService  # noqa: E402
from mt5_agent.application.order_service import OrderService  # noqa: E402
from mt5_agent.application.position_service import PositionService  # noqa: E402
from mt5_agent.application.strategy_service import StrategyService  # noqa: E402
from mt5_agent.config.loader import load_settings  # noqa: E402
from mt5_agent.domain.execution import ExecutionMode  # noqa: E402
from mt5_agent.domain.market import Timeframe  # noqa: E402
from mt5_agent.domain.terminal import MT5Credentials  # noqa: E402
from mt5_agent.execution.executor import MT5TradeExecutor  # noqa: E402
from mt5_agent.infrastructure.mt5.connection_adapter import (  # noqa: E402
    MT5ConnectionAdapter,
)
from mt5_agent.infrastructure.mt5.market_adapter import MT5MarketDataAdapter  # noqa: E402
from mt5_agent.infrastructure.mt5.trading_adapter import (  # noqa: E402
    MT5TradingDataAdapter,
)
from mt5_agent.logging_utils import configure_logging, get_logger  # noqa: E402
from mt5_agent.memory.memories import (  # noqa: E402
    ShortTermMemory,
    StrategyMemory,
    TradeMemory,
    WorldMemory,
)
from mt5_agent.memory.sqlite_store import SQLiteMemoryStore  # noqa: E402
from mt5_agent.risk.supervisor import Supervisor  # noqa: E402
from mt5_agent.strategies.measure_move import DonchianBreakoutStrategy  # noqa: E402
from mt5_agent.strategies.null_strategy import NullStrategy  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the trading agent (read-only unless demo).")
    parser.add_argument("--symbols", default=None)
    parser.add_argument("--timeframe", default="M1")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=float, default=None)
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(level=settings.log_level, log_format=settings.log_format)
    logger = get_logger("run_agent")

    symbols = [s.strip() for s in (args.symbols or settings.agent_symbols).split(",") if s.strip()]
    try:
        timeframe = Timeframe(args.timeframe.strip().upper())
    except ValueError:
        print(json.dumps({"error": f"unsupported timeframe: {args.timeframe}"}))
        return 2

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
    try:
        market = MarketService(MT5MarketDataAdapter(connection=conn))
        trading = MT5TradingDataAdapter(connection=conn)
        account = AccountService(conn, trading, trading)
        observer = Observer(market, account, PositionService(trading), OrderService(trading))
        short_term = ShortTermMemory(store, keep_last=settings.memory_short_term_keep)
        trade_memory = TradeMemory(store, keep_last=settings.memory_trade_keep)
        strategy_memory = StrategyMemory(store, keep_last=settings.memory_strategy_keep)
        world_memory = WorldMemory(store, keep_last=settings.memory_world_keep)
        builder = ContextBuilder(
            StrategyService([NullStrategy(), DonchianBreakoutStrategy()]),
            strategy_memory,
            trade_memory,
        )
        try:
            planner: LLMPlanner | None = LLMPlanner(provider_from_settings(settings))
        except Exception as exc:
            logger.info("LLM not configured; planner falls back to HOLD: %s", exc)
            planner = None
        mode = ExecutionMode(str(settings.execution_mode).upper())
        executor = MT5TradeExecutor(
            mode=mode,
            allow_live=bool(settings.enable_live_trading),
            connection=conn,
            default_volume=settings.execution_default_volume,
            magic=settings.execution_magic,
            deviation=settings.execution_deviation,
        )
        agent = TradingAgent(
            observer=observer,
            context_builder=builder,
            planner=planner,
            supervisor=Supervisor(config=settings.to_risk_config()),
            executor=executor,
            short_term=short_term,
            trade_memory=trade_memory,
            strategy_memory=strategy_memory,
            world_memory=world_memory,
            candle_count=settings.agent_candle_count,
        )

        def _stop(signum: int, frame: object) -> None:  # noqa: ANN001, ANN202
            logger.info("shutdown requested")
            agent.stop()

        signal.signal(signal.SIGINT, _stop)
        try:
            signal.signal(signal.SIGTERM, _stop)
        except (AttributeError, ValueError, OSError):
            pass

        if args.loop:
            cycles = agent.run(
                symbols,
                timeframe,
                interval_s=args.interval
                if args.interval is not None
                else settings.agent_interval_s,
            )
        else:
            cycles = agent.run(symbols, timeframe, interval_s=0, max_cycles=args.cycles)
        print(
            json.dumps(
                [
                    {
                        "cycle": c.cycle_id,
                        "symbol": c.symbol,
                        "ok": c.ok,
                        "stages": [
                            {"stage": s.stage.value, "status": s.status.value, "summary": s.summary}
                            for s in c.stages
                        ],
                    }
                    for c in cycles
                ],
                indent=2,
                default=str,
            )
        )
        return 0 if all(c.ok for c in cycles) else 1
    except Exception as exc:
        logger.warning("agent run failed", extra={"extra_fields": {"error": str(exc)}})
        print(json.dumps({"error": str(exc)}))
        return 1
    finally:
        store.close()
        connection_service.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
