"""Live trading-state integration test (read-only, skipped by default).

Run with: MT5_AGENT_RUN_LIVE_MT5_TESTS=true pytest tests/integration/ -q
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("MT5_AGENT_RUN_LIVE_MT5_TESTS", "false").lower() != "true",
        reason="live MT5 terminal not requested",
    ),
]


def test_live_trading_state_readonly() -> None:
    from mt5_agent.application.account_service import AccountService
    from mt5_agent.application.connection_service import ConnectionService, RetryPolicy
    from mt5_agent.application.history_service import HistoryService
    from mt5_agent.application.order_service import OrderService
    from mt5_agent.application.position_service import PositionService
    from mt5_agent.config.loader import load_settings
    from mt5_agent.infrastructure.mt5.connection_adapter import MT5ConnectionAdapter
    from mt5_agent.infrastructure.mt5.trading_adapter import MT5TradingDataAdapter

    settings = load_settings()
    conn = MT5ConnectionAdapter()
    svc = ConnectionService(conn, RetryPolicy(max_attempts=1, delay_seconds=0))
    try:
        svc.ensure_connected(settings.to_connection_config())
    except Exception as exc:
        pytest.skip(f"MT5 terminal unavailable: {exc}")
        return
    try:
        trading = MT5TradingDataAdapter(connection=conn)
        state = AccountService(conn, trading, trading).get_state()
        assert state.balance >= 0
        assert state.open_positions >= 0
        assert isinstance(PositionService(trading).floating_profit(), float)
        assert isinstance(OrderService(trading).count(), int)
        now = datetime.now(UTC)
        deals = HistoryService(trading).deals(now - timedelta(days=7), now)
        assert isinstance(deals, list)
    finally:
        svc.disconnect()
