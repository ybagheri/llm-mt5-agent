"""ConnectionService tests (port doubles; no MT5, no sleeping)."""

from __future__ import annotations

import pytest

from mt5_agent.application.connection_service import ConnectionService, RetryPolicy
from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.errors import MT5ConnectionError
from mt5_agent.domain.ports import MT5ConnectionPort
from mt5_agent.domain.terminal import (
    ConnectionConfig,
    ConnectionHealth,
    MT5Credentials,
    TerminalInfo,
)


class FakePort(MT5ConnectionPort):
    def __init__(self, failures_before_success: int = 0) -> None:
        self.failures_before_success = failures_before_success
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.connected = False

    def connect(
        self,
        config: ConnectionConfig,
        credentials: MT5Credentials | None = None,
    ) -> None:
        self.connect_calls += 1
        if self.connect_calls <= self.failures_before_success:
            raise MT5ConnectionError("boom")
        self.connected = True

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    def get_account_info(self) -> AccountInfo:
        return AccountInfo(1, "S", "USD", 1.0, 1.0, 0.0, 1.0, 0.0)

    def get_terminal_info(self) -> TerminalInfo:
        return TerminalInfo(connected=True, trade_allowed=True)

    def check_health(self) -> ConnectionHealth:
        return ConnectionHealth(connected=self.connected, trade_allowed=True)


def test_ensure_connected_retries_then_succeeds() -> None:
    port = FakePort(failures_before_success=2)
    svc = ConnectionService(port, RetryPolicy(max_attempts=3, delay_seconds=0))
    health = svc.ensure_connected(ConnectionConfig())
    assert health.connected is True
    assert port.connect_calls == 3


def test_ensure_connected_raises_after_exhaustion() -> None:
    port = FakePort(failures_before_success=99)
    svc = ConnectionService(port, RetryPolicy(max_attempts=2, delay_seconds=0))
    with pytest.raises(MT5ConnectionError):
        svc.ensure_connected(ConnectionConfig())
    assert port.connect_calls == 2


def test_reconnect_disconnects_first() -> None:
    port = FakePort()
    svc = ConnectionService(port, RetryPolicy(max_attempts=1, delay_seconds=0))
    svc.reconnect(ConnectionConfig())
    assert port.disconnect_calls == 1
    assert port.connect_calls == 1


def test_retry_policy_validation() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(delay_seconds=-1.0)


def test_service_read_passthrough() -> None:
    port = FakePort()
    svc = ConnectionService(port, RetryPolicy(max_attempts=1, delay_seconds=0))
    svc.ensure_connected(ConnectionConfig())
    assert svc.get_account().login == 1
    assert svc.get_terminal().connected is True
    assert svc.health().connected is True
