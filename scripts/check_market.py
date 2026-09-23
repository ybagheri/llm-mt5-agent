"""Read-only market snapshot probe (Phase 02). Never trades."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mt5_agent.application.connection_service import (  # noqa: E402
    ConnectionService,
    RetryPolicy,
)
from mt5_agent.application.market_service import MarketService  # noqa: E402
from mt5_agent.config.loader import load_settings  # noqa: E402
from mt5_agent.domain.market import Timeframe  # noqa: E402
from mt5_agent.domain.terminal import MT5Credentials  # noqa: E402
from mt5_agent.infrastructure.mt5.connection_adapter import (  # noqa: E402
    MT5ConnectionAdapter,
)
from mt5_agent.infrastructure.mt5.market_adapter import MT5MarketDataAdapter  # noqa: E402
from mt5_agent.logging_utils import configure_logging, get_logger  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only MT5 market snapshot.")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--timeframe", default=None)
    parser.add_argument("--count", type=int, default=None)
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(level=settings.log_level, log_format=settings.log_format)
    logger = get_logger("check_market")

    symbol = (args.symbol or settings.mt5_default_symbol).strip()
    tf_name = (args.timeframe or settings.mt5_default_timeframe).strip().upper()
    count = args.count or settings.mt5_default_candles
    try:
        timeframe = Timeframe(tf_name)
    except ValueError:
        print(json.dumps({"error": f"unsupported timeframe: {tf_name}"}))
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
    try:
        market = MarketService(MT5MarketDataAdapter(connection=conn))
        snap = market.get_snapshot(symbol, timeframe, count=count)
        print(
            json.dumps(
                {
                    "symbol": snap.symbol,
                    "timeframe": snap.timeframe.value,
                    "fetched_at": snap.fetched_at.isoformat(),
                    "candles": len(snap.candles),
                    "latest_close": snap.latest_close,
                    "tick": (
                        {
                            "bid": snap.tick.bid,
                            "ask": snap.tick.ask,
                            "spread": snap.tick.spread,
                            "time": snap.tick.time.isoformat(),
                        }
                        if snap.tick
                        else None
                    ),
                    "symbol_info": (
                        {
                            "digits": snap.symbol_info.digits,
                            "spread": snap.symbol_info.spread,
                            "currency_base": snap.symbol_info.currency_base,
                        }
                        if snap.symbol_info
                        else None
                    ),
                },
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        logger.warning("market fetch failed", extra={"extra_fields": {"error": str(exc)}})
        print(json.dumps({"error": str(exc)}))
        return 1
    finally:
        connection_service.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
