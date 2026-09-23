"""Domain ports (interfaces) for MT5 connectivity and market data.

The domain defines *what* is needed; `infrastructure/mt5/` provides the
MetaTrader5-backed implementations. Domain code never imports MetaTrader5.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.market import Candle, MarketSnapshot, SymbolInfo, Tick, Timeframe
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


class MarketDataPort(ABC):
    """Abstract market-data source. Strategies consume domain models only."""

    @abstractmethod
    def get_tick(self, symbol: str) -> Tick:
        """Return the latest tick; raises on unknown symbol / fetch failure."""
        ...

    @abstractmethod
    def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        count: int = 100,
        start_pos: int = 0,
    ) -> list[Candle]:
        """Return newest-last candles; raises on invalid args / fetch failure."""
        ...

    @abstractmethod
    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """Return symbol metadata; raises on unknown symbol."""
        ...

    @abstractmethod
    def get_snapshot(
        self,
        symbol: str,
        timeframe: Timeframe,
        count: int = 100,
    ) -> MarketSnapshot:
        """Compose tick + candles + symbol info (tick/symbol best-effort)."""
        ...


__all__ = ["MT5ConnectionPort", "MarketDataPort"]
