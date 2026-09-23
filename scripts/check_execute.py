"""Execution probe: DRY_RUN default; DEMO only with --mode demo (never LIVE)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mt5_agent.application.account_service import AccountService  # noqa: E402
from mt5_agent.application.connection_service import (  # noqa: E402
    ConnectionService,
    RetryPolicy,
)
from mt5_agent.application.market_service import MarketService  # noqa: E402
from mt5_agent.application.strategy_service import StrategyService  # noqa: E402
from mt5_agent.config.loader import load_settings  # noqa: E402
from mt5_agent.domain.execution import ExecutionMode  # noqa: E402
from mt5_agent.domain.market import Timeframe  # noqa: E402
from mt5_agent.domain.planning import PlannerInput  # noqa: E402
from mt5_agent.domain.strategy import MarketContext  # noqa: E402
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
from mt5_agent.risk.context import RiskContext  # noqa: E402
from mt5_agent.risk.supervisor import Supervisor  # noqa: E402
from mt5_agent.strategies.measure_move import DonchianBreakoutStrategy  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe execution (dry_run default).")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--mode", default="dry_run", choices=["dry_run", "demo"])
    parser.add_argument("--client-id", default=None)
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(level=settings.log_level, log_format=settings.log_format)
    logger = get_logger("check_execute")
    symbol = (args.symbol or settings.mt5_default_symbol).strip()

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
    try:
        market = MarketService(MT5MarketDataAdapter(connection=conn))
        trading = MT5TradingDataAdapter(connection=conn)
        snap = market.get_snapshot(symbol, Timeframe.M1, count=30)
        ctx = MarketContext(symbol, Timeframe.M1, snap)
        (signal,) = StrategyService([DonchianBreakoutStrategy()]).analyze(ctx)
        # Fixed probe intent: tiny order honouring the live signal direction when
        # directional, else HOLD (executor rejects HOLD safely).
        from mt5_agent.ai.planner import hold_proposal  # noqa: E402
        from mt5_agent.domain.planning import TradeAction, TradeProposal  # noqa: E402
        from mt5_agent.domain.strategy import Direction  # noqa: E402

        if signal.direction == Direction.FLAT:
            proposal = hold_proposal(
                PlannerInput(symbol, Timeframe.M1, snap, signal), "probe: no signal"
            )
        else:
            close = snap.latest_close or 0.0
            action = TradeAction.BUY if signal.direction == Direction.LONG else TradeAction.SELL
            sl = close * 0.999 if action == TradeAction.BUY else close * 1.001
            tp = close * 1.002 if action == TradeAction.BUY else close * 0.998
            proposal = TradeProposal(
                action=action,
                symbol=symbol,
                confidence=0.5,
                rationale="probe",
                strategy=signal.strategy,
                entry=close,
                stop_loss=sl,
                take_profit=tp,
                risk_pct=0.25,
                volume=settings.execution_default_volume,
            )
        state = AccountService(conn, trading, trading).get_state()
        tick = market.get_tick(symbol)
        info = market.get_symbol_info(symbol)
        spread = (tick.ask - tick.bid) / info.point if info.point > 0 else None
        from datetime import UTC, datetime  # noqa: E402

        context = RiskContext(
            account=state,
            positions=tuple(trading.get_open_positions()),
            orders=tuple(trading.get_pending_orders()),
            spreads_points={symbol: spread} if spread is not None else {},
            symbol_points={symbol: info.point},
            server_time=datetime.now(UTC),
        )
        decision = Supervisor(config=settings.to_risk_config()).review(proposal, context)
        mode = ExecutionMode.DEMO if args.mode == "demo" else ExecutionMode.DRY_RUN
        if mode == ExecutionMode.DEMO and settings.trading_mode == "live":
            print(json.dumps({"error": "refusing DEMO probe while trading_mode=live"}))
            return 2
        executor = MT5TradeExecutor(
            mode=mode,
            connection=conn,
            default_volume=settings.execution_default_volume,
            magic=settings.execution_magic,
            deviation=settings.execution_deviation,
        )
        record = executor.execute(decision, client_id=args.client_id or "probe-1")
        print(
            json.dumps(
                {
                    "signal": signal.direction.value,
                    "approved": decision.approved,
                    "codes": list(decision.codes),
                    "record": {
                        "status": record.status.value,
                        "mode": record.mode.value,
                        "ticket": record.ticket,
                        "deal": record.deal,
                        "executed_price": record.executed_price,
                        "slippage": record.slippage,
                        "error_code": record.error_code,
                        "message": record.message,
                    },
                },
                indent=2,
                default=str,
            )
        )
        return 0
    except Exception as exc:
        logger.warning("execute probe failed", extra={"extra_fields": {"error": str(exc)}})
        print(json.dumps({"error": str(exc)}))
        return 1
    finally:
        connection_service.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
