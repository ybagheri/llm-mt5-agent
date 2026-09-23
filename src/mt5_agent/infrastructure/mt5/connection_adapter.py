"""MT5 connection adapter: the ONLY module that calls the MT5 terminal.

Wraps the official ``MetaTrader5`` package behind :class:`MT5ConnectionPort`.
Polling/sync/execution concerns stay behind this interface so an optional
MQL5 event bridge can be introduced later without touching domain code.

Read-only in Phase 01: initialize/login/shutdown/terminal_info/account_info.
No order-sending code lives here.
"""

from __future__ import annotations

import threading
from typing import Any

from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.errors import (
    MT5ConnectionError,
    MT5DataError,
    MT5Error,
    MT5LoginError,
    MT5NotConnectedError,
)
from mt5_agent.domain.ports import MT5ConnectionPort
from mt5_agent.domain.terminal import (
    ConnectionConfig,
    ConnectionHealth,
    MT5Credentials,
    TerminalInfo,
)
from mt5_agent.infrastructure.mt5.mappers import map_account_info, map_terminal_info
from mt5_agent.infrastructure.mt5.module import load_mt5


class MT5ConnectionAdapter(MT5ConnectionPort):
    """MT5-backed connection. Inject a fake `mt5_module` in tests."""

    def __init__(self, mt5_module: Any | None = None) -> None:
        self._mt5: Any | None = mt5_module
        self._lock = threading.Lock()
        self._connected = False

    # -- lifecycle -----------------------------------------------------
    def connect(
        self,
        config: ConnectionConfig,
        credentials: MT5Credentials | None = None,
    ) -> None:
        mt5 = self._require_module()
        kwargs: dict[str, Any] = {
            "timeout": int(config.timeout_ms),
            "portable": bool(config.portable),
        }
        path = config.path or None
        login = credentials.login if credentials else config.login
        password = credentials.password if credentials else None
        server = credentials.server if credentials else config.server
        if login is not None:
            kwargs["login"] = int(login)
        if password is not None:
            kwargs["password"] = str(password)
        if server is not None:
            kwargs["server"] = str(server)

        with self._lock:
            ok = mt5.initialize(path, **kwargs) if path else mt5.initialize(**kwargs)
            if not ok:
                raise MT5ConnectionError(
                    f"mt5.initialize() failed: {self._last_error(mt5)}",
                    code=self._last_error(mt5),
                )
            # Explicit login() only when credentials were supplied; initialize()
            # alone connects to the terminal's last-used account otherwise.
            if credentials is not None:
                if not mt5.login(credentials.login, password=password, server=server):
                    try:
                        mt5.shutdown()
                    finally:
                        pass
                    raise MT5LoginError(
                        f"mt5.login() failed for login={credentials.login} "
                        f"server={credentials.server!r}: {self._last_error(mt5)}",
                        code=self._last_error(mt5),
                    )
            self._connected = True

    def disconnect(self) -> None:
        mt5 = self._mt5
        with self._lock:
            try:
                if mt5 is not None:
                    mt5.shutdown()
            finally:
                self._connected = False

    def is_connected(self) -> bool:
        return bool(self._connected)

    # -- read-only probes ----------------------------------------------
    def get_account_info(self) -> AccountInfo:
        mt5 = self._ensure_connected()
        raw = mt5.account_info()
        if raw is None:
            raise MT5DataError(
                f"account_info() returned None: {self._last_error(mt5)}",
            )
        return map_account_info(raw)

    def get_terminal_info(self) -> TerminalInfo:
        mt5 = self._ensure_connected()
        raw = mt5.terminal_info()
        if raw is None:
            raise MT5DataError(
                f"terminal_info() returned None: {self._last_error(mt5)}",
            )
        return map_terminal_info(raw)

    def check_health(self) -> ConnectionHealth:
        """Fail-safe probe: never raises; reports problems in the record."""
        try:
            if not self._connected:
                return ConnectionHealth(connected=False, error="not connected")
            self._require_module()
            terminal = self.get_terminal_info()
            try:
                account = self.get_account_info()
                account_login: int | None = account.login
            except MT5Error:
                account_login = None
            connected = bool(terminal.connected and self._connected)
            return ConnectionHealth(
                connected=connected,
                trade_allowed=bool(terminal.trade_allowed),
                account_login=account_login,
                terminal_company=terminal.company,
                error="" if connected else "terminal reports disconnected",
            )
        except Exception as exc:  # health must never raise
            return ConnectionHealth(connected=False, error=str(exc))

    # -- internals ------------------------------------------------------
    def _require_module(self) -> Any:
        if self._mt5 is None:
            self._mt5 = load_mt5()
        return self._mt5

    def _ensure_connected(self) -> Any:
        mt5 = self._require_module()
        if not self._connected:
            raise MT5NotConnectedError("Not connected. Call connect() first.")
        return mt5

    @staticmethod
    def _last_error(mt5: Any) -> Any:
        try:
            return mt5.last_error()
        except Exception:
            return "unknown error"


__all__ = ["MT5ConnectionAdapter"]
