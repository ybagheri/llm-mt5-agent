"""Market domain models (pure — no MT5 dependency).

Strategies consume these models, never raw MT5 tuples/arrays.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class Timeframe(StrEnum):
    """Supported candle timeframes (subset of MT5 timeframes)."""

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"
    MN1 = "MN1"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class Tick:
    """Latest quote for a symbol."""

    symbol: str
    time: datetime
    bid: float
    ask: float
    last: float = 0.0
    volume: float = 0.0

    def __post_init__(self) -> None:
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if self.bid <= 0 or self.ask <= 0:
            raise ValueError("bid/ask must be positive")
        if self.ask < self.bid:
            raise ValueError("ask must be >= bid")
        object.__setattr__(self, "time", _utc(self.time))

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0


@dataclass(frozen=True, slots=True)
class Candle:
    """Single OHLC bar."""

    symbol: str
    timeframe: Timeframe
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int = 0
    spread: int = 0
    real_volume: float = 0.0

    def __post_init__(self) -> None:
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        for name in ("open", "high", "low", "close"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("high/low inconsistent with open/close")
        object.__setattr__(self, "time", _utc(self.time))

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low


@dataclass(frozen=True, slots=True)
class SymbolInfo:
    """Symbol metadata (read-only)."""

    symbol: str
    description: str = ""
    currency_base: str = ""
    currency_profit: str = ""
    digits: int = 0
    point: float = 0.0
    spread: int = 0
    trade_mode: int = 0
    min_volume: float = 0.0
    max_volume: float = 0.0
    volume_step: float = 0.0
    contract_size: float = 0.0

    def __post_init__(self) -> None:
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol must be non-empty")


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """Point-in-time market view strategies reason over."""

    symbol: str
    timeframe: Timeframe
    fetched_at: datetime
    candles: tuple[Candle, ...] = ()
    tick: Tick | None = None
    symbol_info: SymbolInfo | None = None
    details: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        object.__setattr__(self, "fetched_at", _utc(self.fetched_at))

    @property
    def latest_candle(self) -> Candle | None:
        return self.candles[-1] if self.candles else None

    @property
    def latest_close(self) -> float | None:
        latest = self.latest_candle
        return latest.close if latest else None


__all__ = ["Candle", "MarketSnapshot", "SymbolInfo", "Tick", "Timeframe"]
