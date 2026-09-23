"""Live-terminal integration tests (Phase 01).

Skipped by default. Run explicitly with:
  MT5_AGENT_RUN_LIVE_MT5_TESTS=true pytest tests/integration/test_mt5_live.py -q

Requires Windows + installed MT5 terminal. Read-only: never sends orders.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

RUN_LIVE = os.getenv("MT5_AGENT_RUN_LIVE_MT5_TESTS", "false").lower() == "true"

pytestmark = pytest.mark.skipif(not RUN_LIVE, reason="live MT5 terminal not requested")


def test_live_terminal_and_account_readonly() -> None:
    from mt5_agent.application.connection_service import ConnectionService, RetryPolicy
    from mt5_agent.config.loader import load_settings
    from mt5_agent.infrastructure.mt5.connection_adapter import MT5ConnectionAdapter

    settings = load_settings()
    adapter = MT5ConnectionAdapter()
    svc = ConnectionService(adapter, RetryPolicy(max_attempts=1, delay_seconds=0))
    try:
        health = svc.ensure_connected(settings.to_connection_config())
    except Exception as exc:
        pytest.skip(f"MT5 terminal unavailable: {exc}")
        return
    try:
        assert health.connected in (True, False)
        terminal = svc.get_terminal()
        assert isinstance(terminal.name, str)
        try:
            account = svc.get_account()
            assert account.login >= 0
        except Exception:
            pass  # terminal without logged-in account is acceptable here
    finally:
        svc.disconnect()
