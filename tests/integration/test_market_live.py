"""Live market-data integration test (read-only, skipped by default).

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


def test_live_market_snapshot_readonly() -> None:
    from mt5_agent.application.connection_service import ConnectionService, RetryPolicy
    from mt5_agent.application.market_service import MarketService
    from mt5_agent.config.loader import load_settings
    from mt5_agent.domain.market import Timeframe
    from mt5_agent.infrastructure.mt5.connection_adapter import MT5ConnectionAdapter
    from mt5_agent.infrastructure.mt5.market_adapter import MT5MarketDataAdapter

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
        symbol = settings.mt5_default_symbol
        snap = market.get_snapshot(symbol, Timeframe.M1, count=5)
        assert snap.symbol == symbol
        assert len(snap.candles) >= 1
        assert snap.tick is not None
        assert snap.tick.ask >= snap.tick.bid > 0
    finally:
        svc.disconnect()
