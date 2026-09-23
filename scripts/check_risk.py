"""Risk probe: build a proposal, validate against live state (never executes)."""

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
from mt5_agent.config.loader import load_settings  # noqa: E402
from mt5_agent.domain.planning import TradeAction, TradeProposal  # noqa: E402
from mt5_agent.domain.terminal import MT5Credentials  # noqa: E402
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a proposal vs live state.")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--action", default="HOLD", choices=["BUY", "SELL", "HOLD"])
    parser.add_argument("--entry", type=float, default=None)
    parser.add_argument("--stop-loss", type=float, default=None)
    parser.add_argument("--take-profit", type=float, default=None)
    parser.add_argument("--risk-pct", type=float, default=0.5)
    parser.add_argument("--volume", type=float, default=0.01)
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(level=settings.log_level, log_format=settings.log_format)
    logger = get_logger("check_risk")
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
        trading = MT5TradingDataAdapter(connection=conn)
        market = MarketService(MT5MarketDataAdapter(connection=conn))
        state = AccountService(conn, trading, trading).get_state()
        action = TradeAction(args.action)
        actionable = action in (TradeAction.BUY, TradeAction.SELL)
        proposal = TradeProposal(
            action=action,
            symbol=symbol,
            confidence=0.5 if actionable else 0.0,
            rationale="manual probe",
            strategy="check_risk",
            entry=args.entry,
            stop_loss=args.stop_loss,
            take_profit=args.take_profit,
            risk_pct=args.risk_pct if actionable else 0.0,
            volume=args.volume if actionable else None,
        )
        tick = market.get_tick(symbol)
        info = market.get_symbol_info(symbol)
        spread_points = (tick.ask - tick.bid) / info.point if info.point > 0 else None
        from datetime import UTC, datetime  # noqa: E402

        context = RiskContext(
            account=state,
            positions=tuple(trading.get_open_positions()),
            orders=tuple(trading.get_pending_orders()),
            spreads_points={symbol: spread_points} if spread_points is not None else {},
            symbol_points={symbol: info.point},
            server_time=datetime.now(UTC),
            day_pnl=None,
        )
        supervisor = Supervisor(config=settings.to_risk_config())
        decision = supervisor.review(proposal, context)
        print(
            json.dumps(
                {
                    "approved": decision.approved,
                    "codes": list(decision.codes),
                    "violations": [
                        {"code": v.code.value, "message": v.message}
                        for v in decision.result.violations
                    ],
                    "account": {
                        "balance": state.balance,
                        "equity": state.equity,
                        "open_positions": state.open_positions,
                    },
                },
                indent=2,
                default=str,
            )
        )
        return 0
    except Exception as exc:
        logger.warning("risk probe failed", extra={"extra_fields": {"error": str(exc)}})
        print(json.dumps({"error": str(exc)}))
        return 1
    finally:
        connection_service.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
