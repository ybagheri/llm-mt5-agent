"""Strategy probe: fetch snapshot, run strategies, print signals (read-only)."""

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
from mt5_agent.application.strategy_service import StrategyService  # noqa: E402
from mt5_agent.config.loader import load_settings  # noqa: E402
from mt5_agent.domain.market import Timeframe  # noqa: E402
from mt5_agent.domain.strategy import MarketContext  # noqa: E402
from mt5_agent.domain.terminal import MT5Credentials  # noqa: E402
from mt5_agent.infrastructure.mt5.connection_adapter import (  # noqa: E402
    MT5ConnectionAdapter,
)
from mt5_agent.infrastructure.mt5.market_adapter import MT5MarketDataAdapter  # noqa: E402
from mt5_agent.logging_utils import configure_logging, get_logger  # noqa: E402
from mt5_agent.strategies.measure_move import (  # noqa: E402
    DonchianBreakoutStrategy,
    MeasureMoveParams,
)
from mt5_agent.strategies.null_strategy import NullStrategy  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic strategies (read-only).")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--timeframe", default=None)
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--lookback", type=int, default=20)
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(level=settings.log_level, log_format=settings.log_format)
    logger = get_logger("check_strategy")

    symbol = (args.symbol or settings.mt5_default_symbol).strip()
    tf_name = (args.timeframe or settings.mt5_default_timeframe).strip().upper()
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
        snap = market.get_snapshot(symbol, timeframe, count=args.count)
        ctx = MarketContext(symbol, timeframe, snap)
        service = StrategyService(
            [NullStrategy(), DonchianBreakoutStrategy(MeasureMoveParams(lookback=args.lookback))]
        )
        print(
            json.dumps(
                [
                    {
                        "strategy": s.strategy,
                        "direction": s.direction.value,
                        "confidence": s.confidence,
                        "setups": [st.identifier for st in s.setups],
                        "facts": s.facts,
                        "rationale": s.rationale,
                    }
                    for s in service.analyze(ctx)
                ]
                + [
                    {
                        "decisions": [
                            {
                                "strategy": d.signal.strategy,
                                "action": d.action.value,
                                "reasons": list(d.reasons),
                            }
                            for d in service.decide(ctx)
                        ]
                    }
                ],
                indent=2,
                default=str,
            )
        )
        return 0
    except Exception as exc:
        logger.warning("strategy probe failed", extra={"extra_fields": {"error": str(exc)}})
        print(json.dumps({"error": str(exc)}))
        return 1
    finally:
        connection_service.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
