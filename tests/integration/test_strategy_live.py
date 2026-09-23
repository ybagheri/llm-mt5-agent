"""Live strategy integration test (read-only, skipped by default).

Run with: MT5_AGENT_RUN_LIVE_MT5_TESTS=true pytest tests/integration/ -q
"""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("MT5_AGENT_RUN_LIVE_MT5_TESTS", "false").lower() != "true",
        reason="live MT5 terminal not requested",
    ),
]


def test_live_strategies_observe_only() -> None:
    from mt5_agent.application.connection_service import ConnectionService, RetryPolicy
    from mt5_agent.application.market_service import MarketService
    from mt5_agent.application.strategy_service import StrategyService
    from mt5_agent.config.loader import load_settings
    from mt5_agent.domain.market import Timeframe
    from mt5_agent.domain.strategy import MarketContext
    from mt5_agent.infrastructure.mt5.connection_adapter import MT5ConnectionAdapter
    from mt5_agent.infrastructure.mt5.market_adapter import MT5MarketDataAdapter
    from mt5_agent.strategies.measure_move import DonchianBreakoutStrategy
    from mt5_agent.strategies.null_strategy import NullStrategy

    settings = load_settings()
    conn = MT5ConnectionAdapter()
    svc = ConnectionService(conn, RetryPolicy(max_attempts=1, delay_seconds=0))
    try:
        svc.ensure_connected(settings.to_connection_config())
    except Exception as exc:
        pytest.skip(f"MT5 terminal unavailable: {exc}")
        return
    try:
        market = MarketService(MT5MarketDataAdapter(connection=conn))
        snap = market.get_snapshot(settings.mt5_default_symbol, Timeframe.M1, count=30)
        ctx = MarketContext(snap.symbol, snap.timeframe, snap)
        service = StrategyService([NullStrategy(), DonchianBreakoutStrategy()])
        signals = service.analyze(ctx)
        assert len(signals) == 2
        # NullStrategy invariant holds live too.
        assert signals[0].direction.value == "FLAT"
    finally:
        svc.disconnect()
