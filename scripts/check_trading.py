"""Read-only trading-state probe (Phase 03). Never trades, never sends orders."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mt5_agent.application.account_service import AccountService  # noqa: E402
from mt5_agent.application.connection_service import (  # noqa: E402
    ConnectionService,
    RetryPolicy,
)
from mt5_agent.application.history_service import HistoryService  # noqa: E402
from mt5_agent.config.loader import load_settings  # noqa: E402
from mt5_agent.domain.terminal import MT5Credentials  # noqa: E402
from mt5_agent.infrastructure.mt5.connection_adapter import (  # noqa: E402
    MT5ConnectionAdapter,
)
from mt5_agent.infrastructure.mt5.trading_adapter import (  # noqa: E402
    MT5TradingDataAdapter,
)
from mt5_agent.logging_utils import configure_logging, get_logger  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only MT5 trading-state probe.")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(level=settings.log_level, log_format=settings.log_format)
    logger = get_logger("check_trading")

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
        state = AccountService(conn, trading, trading).get_state()
        now = datetime.now(UTC)
        deals = HistoryService(trading).recent_deals(days=args.days)
        results = HistoryService(trading).closed_results(deals)
        print(
            json.dumps(
                {
                    "account": {
                        "login": state.account.login,
                        "server": state.account.server,
                        "currency": state.account.currency,
                        "balance": state.balance,
                        "equity": state.equity,
                        "margin": state.margin,
                        "free_margin": state.free_margin,
                        "margin_level": state.margin_level,
                        "floating_profit": state.floating_profit,
                    },
                    "open_positions": state.open_positions,
                    "pending_orders": state.pending_orders,
                    "exposure_volume": state.exposure_volume,
                    "net_volume": state.net_volume,
                    "positions": [
                        {
                            "ticket": p.ticket,
                            "symbol": p.symbol,
                            "side": p.side.name,
                            "volume": p.volume,
                            "profit": p.profit,
                        }
                        for p in trading.get_open_positions()
                    ],
                    "pending": [
                        {"ticket": o.ticket, "symbol": o.symbol, "type": o.order_type}
                        for o in trading.get_pending_orders()
                    ],
                    "recent_deals": len(deals),
                    "closed_trades": len(results),
                    "realized_net": sum(r.net for r in results),
                    "window_days": args.days,
                    "window_from": (now - timedelta(days=args.days)).isoformat(),
                },
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        logger.warning("trading fetch failed", extra={"extra_fields": {"error": str(exc)}})
        print(json.dumps({"error": str(exc)}))
        return 1
    finally:
        connection_service.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
