"""Planner probe: snapshot + signal -> proposal (offline --stub or live LLM)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mt5_agent.ai.factory import provider_from_settings  # noqa: E402
from mt5_agent.ai.models import LLMRequest, LLMResponse, LLMUsage  # noqa: E402
from mt5_agent.ai.planner import LLMPlanner  # noqa: E402
from mt5_agent.ai.provider import LLMProvider  # noqa: E402
from mt5_agent.application.connection_service import (  # noqa: E402
    ConnectionService,
    RetryPolicy,
)
from mt5_agent.application.market_service import MarketService  # noqa: E402
from mt5_agent.application.strategy_service import StrategyService  # noqa: E402
from mt5_agent.config.loader import load_settings  # noqa: E402
from mt5_agent.domain.market import Timeframe  # noqa: E402
from mt5_agent.domain.planning import PlannerInput  # noqa: E402
from mt5_agent.domain.strategy import MarketContext  # noqa: E402
from mt5_agent.domain.terminal import MT5Credentials  # noqa: E402
from mt5_agent.infrastructure.mt5.connection_adapter import (  # noqa: E402
    MT5ConnectionAdapter,
)
from mt5_agent.infrastructure.mt5.market_adapter import MT5MarketDataAdapter  # noqa: E402
from mt5_agent.logging_utils import configure_logging, get_logger  # noqa: E402
from mt5_agent.strategies.measure_move import DonchianBreakoutStrategy  # noqa: E402
from mt5_agent.strategies.null_strategy import NullStrategy  # noqa: E402


class StubProvider(LLMProvider):
    """Offline deterministic stand-in (mirrors the signal direction)."""

    name = "stub"

    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    @property
    def model(self) -> str:
        return "stub-1"

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        payload = json.loads(request.messages[-1].content)["strategy_signal"]
        direction = payload["direction"]
        if direction == "FLAT":
            text = json.dumps(
                {
                    "action": "HOLD",
                    "confidence": 0.0,
                    "rationale": "stub: no direction",
                    "risk_pct": 0.0,
                }
            )
        else:
            close = payload["facts"].get("latest_close", 1.0)
            sl = close * 0.999 if direction == "LONG" else close * 1.001
            tp = close * 1.002 if direction == "LONG" else close * 0.998
            text = json.dumps(
                {
                    "action": direction,
                    "entry": close,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "risk_pct": 0.25,
                    "confidence": 0.5,
                    "rationale": f"stub mirrors {direction}",
                }
            )
        return LLMResponse(text, "stub", "stub-1", 0.1, LLMUsage(), structured=json.loads(text))


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe the planner (read-only).")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--timeframe", default=None)
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--stub", action="store_true", help="Use offline stub LLM.")
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(level=settings.log_level, log_format=settings.log_format)
    logger = get_logger("check_plan")

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
        signals = StrategyService([NullStrategy(), DonchianBreakoutStrategy()]).analyze(ctx)
        signal = next(s for s in signals if s.strategy != "null")
        planner_input = PlannerInput(symbol, timeframe, snap, signal)
        provider: LLMProvider = StubProvider() if args.stub else provider_from_settings(settings)
        proposal = LLMPlanner(provider).plan(planner_input)
        print(
            json.dumps(
                {
                    "signal": {
                        "strategy": signal.strategy,
                        "direction": signal.direction.value,
                        "confidence": signal.confidence,
                    },
                    "proposal": {
                        "action": proposal.action.value,
                        "entry": proposal.entry,
                        "stop_loss": proposal.stop_loss,
                        "take_profit": proposal.take_profit,
                        "risk_pct": proposal.risk_pct,
                        "confidence": proposal.confidence,
                        "rationale": proposal.rationale,
                        "strategy": proposal.strategy,
                        "setup_id": proposal.setup_id,
                        "provider": proposal.provider,
                        "model": proposal.model,
                        "latency_ms": round(proposal.latency_ms, 1),
                    },
                },
                indent=2,
                default=str,
            )
        )
        return 0
    except Exception as exc:
        logger.warning("plan probe failed", extra={"extra_fields": {"error": str(exc)}})
        print(json.dumps({"error": str(exc)}))
        return 1
    finally:
        connection_service.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
