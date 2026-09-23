"""Domain ports (interfaces) for MT5 connectivity.

The domain defines *what* is needed; `infrastructure/mt5/` provides the
MetaTrader5-backed implementation. Domain code never imports MetaTrader5.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.terminal import (
    ConnectionConfig,
    ConnectionHealth,
    MT5Credentials,
    TerminalInfo,
)


class MT5ConnectionPort(ABC):
    """Abstract MT5 terminal connection (read-only in Phase 01)."""

    @abstractmethod
    def connect(
        self,
        config: ConnectionConfig,
        credentials: MT5Credentials | None = None,
    ) -> None:
        """Establish terminal connection, optionally logging into an account."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close the terminal connection (idempotent)."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True when a terminal connection is active."""
        ...

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        """Return current account snapshot; raises when unavailable."""
        ...

    @abstractmethod
    def get_terminal_info(self) -> TerminalInfo:
        """Return terminal snapshot; raises when unavailable."""
        ...

    @abstractmethod
    def check_health(self) -> ConnectionHealth:
        """Fail-safe health probe; never raises, reports via `ConnectionHealth`."""
        ...


__all__ = ["MT5ConnectionPort"]
