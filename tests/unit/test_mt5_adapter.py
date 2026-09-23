"""Adapter tests with a FakeMT5 module (no terminal, no MetaTrader5 import)."""

from __future__ import annotations

from collections import namedtuple
from typing import Any

import pytest

from mt5_agent.domain.errors import (
    MT5ConnectionError,
    MT5DataError,
    MT5LoginError,
    MT5NotConnectedError,
)
from mt5_agent.domain.terminal import ConnectionConfig, MT5Credentials
from mt5_agent.infrastructure.mt5.connection_adapter import MT5ConnectionAdapter

AccountTuple = namedtuple(
    "AccountTuple",
    [
        "login",
        "server",
        "currency",
        "balance",
        "equity",
        "margin",
        "margin_free",
        "profit",
        "leverage",
        "trade_allowed",
        "name",
    ],
)
TerminalTuple = namedtuple(
    "TerminalTuple",
    ["company", "name", "path", "trade_allowed", "connected", "build", "maxbars"],
)


class FakeMT5:
    """Minimal in-memory double of the MetaTrader5 module API."""

    def __init__(self) -> None:
        self.init_calls: list[dict[str, Any]] = []
        self.login_calls: list[dict[str, Any]] = []
        self.shutdown_calls = 0
        self.fail_initialize = False
        self.fail_login = False
        self.account_payload: Any = AccountTuple(
            42, "Fake-Server", "USD", 5000.0, 5100.0, 50.0, 5050.0, 100.0, 100, True, "Fake"
        )
        self.terminal_payload: Any = TerminalTuple(
            "FakeCo", "MT5", "C:/fake/terminal64.exe", True, True, 4000, 50000
        )

    def initialize(self, *args: Any, **kwargs: Any) -> bool:
        self.init_calls.append({"args": args, "kwargs": kwargs})
        return not self.fail_initialize

    def login(self, *args: Any, **kwargs: Any) -> bool:
        self.login_calls.append({"args": args, "kwargs": kwargs})
        return not self.fail_login

    def shutdown(self) -> None:
        self.shutdown_calls += 1

    def account_info(self) -> Any:
        return self.account_payload

    def terminal_info(self) -> Any:
        return self.terminal_payload

    def last_error(self) -> Any:
        return (-1, "fake error")


def test_connect_and_read() -> None:
    fake = FakeMT5()
    adapter = MT5ConnectionAdapter(mt5_module=fake)
    adapter.connect(ConnectionConfig(timeout_ms=5000))
    assert adapter.is_connected() is True
    assert adapter.get_account_info().login == 42
    assert adapter.get_terminal_info().company == "FakeCo"
    assert adapter.check_health().connected is True
    adapter.disconnect()
    assert adapter.is_connected() is False
    assert fake.shutdown_calls == 1


def test_connect_with_credentials_calls_login() -> None:
    fake = FakeMT5()
    adapter = MT5ConnectionAdapter(mt5_module=fake)
    creds = MT5Credentials(login=42, password="secret", server="Fake-Server")
    adapter.connect(ConnectionConfig(), creds)
    assert len(fake.login_calls) == 1
    # Credentials must not leak into health details.
    health = adapter.check_health()
    assert "secret" not in str(health)


def test_initialize_failure_raises_connection_error() -> None:
    fake = FakeMT5()
    fake.fail_initialize = True
    adapter = MT5ConnectionAdapter(mt5_module=fake)
    with pytest.raises(MT5ConnectionError):
        adapter.connect(ConnectionConfig())
    assert adapter.is_connected() is False


def test_login_failure_raises_and_shutdowns() -> None:
    fake = FakeMT5()
    fake.fail_login = True
    adapter = MT5ConnectionAdapter(mt5_module=fake)
    with pytest.raises(MT5LoginError):
        adapter.connect(ConnectionConfig(), MT5Credentials(1, "pw", "S"))
    assert adapter.is_connected() is False
    assert fake.shutdown_calls == 1


def test_read_without_connect_raises() -> None:
    adapter = MT5ConnectionAdapter(mt5_module=FakeMT5())
    with pytest.raises(MT5NotConnectedError):
        adapter.get_account_info()


def test_none_payloads_raise_data_error() -> None:
    fake = FakeMT5()
    fake.account_payload = None
    fake.terminal_payload = None
    adapter = MT5ConnectionAdapter(mt5_module=fake)
    adapter.connect(ConnectionConfig())
    with pytest.raises(MT5DataError):
        adapter.get_account_info()
    with pytest.raises(MT5DataError):
        adapter.get_terminal_info()


def test_check_health_never_raises() -> None:
    fake = FakeMT5()
    fake.terminal_payload = None
    adapter = MT5ConnectionAdapter(mt5_module=fake)
    adapter.connect(ConnectionConfig())
    health = adapter.check_health()
    assert health.connected is False
    assert health.error != ""


def test_disconnect_is_idempotent() -> None:
    adapter = MT5ConnectionAdapter(mt5_module=FakeMT5())
    adapter.disconnect()
    adapter.disconnect()
    assert adapter.is_connected() is False


def test_credentials_repr_masks_password() -> None:
    creds = MT5Credentials(login=1, password="super-secret", server="S")
    assert "super-secret" not in repr(creds)
