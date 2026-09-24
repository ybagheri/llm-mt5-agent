"""Trading domain models: positions, orders, deals, account state (pure, read-only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum

from mt5_agent.domain.account import AccountInfo


class PositionSide(IntEnum):
    """Open position direction (MT5 position `type`: 0=BUY, 1=SELL)."""

    BUY = 0
    SELL = 1


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class Position:
    """Open position snapshot (read-only)."""

    ticket: int
    symbol: str
    side: PositionSide
    volume: float
    price_open: float
    price_current: float
    profit: float = 0.0
    swap: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    magic: int = 0
    comment: str = ""
    time: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.ticket <= 0:
            raise ValueError("ticket must be positive")
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if self.volume <= 0:
            raise ValueError("volume must be positive")
        object.__setattr__(self, "time", _utc(self.time))

    @property
    def floating(self) -> float:
        return self.profit + self.swap

    @property
    def signed_volume(self) -> float:
        return self.volume if self.side == PositionSide.BUY else -self.volume


@dataclass(frozen=True, slots=True)
class Order:
    """Pending-order snapshot, incl. history orders (read-only)."""

    ticket: int
    symbol: str
    order_type: int
    volume_current: float
    volume_initial: float
    price_open: float
    stop_loss: float = 0.0
    take_profit: float = 0.0
    price_current: float = 0.0
    magic: int = 0
    comment: str = ""
    time_setup: datetime = field(default_factory=lambda: datetime.now(UTC))
    state: int = 0

    def __post_init__(self) -> None:
        if self.ticket <= 0:
            raise ValueError("ticket must be positive")
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if self.volume_initial < 0 or self.volume_current < 0:
            raise ValueError("volumes must be non-negative")
        object.__setattr__(self, "time_setup", _utc(self.time_setup))


@dataclass(frozen=True, slots=True)
class Deal:
    """Historical deal snapshot (read-only)."""

    ticket: int
    order_ticket: int
    position_id: int
    symbol: str
    deal_type: int
    entry: int
    volume: float
    price: float
    profit: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    fee: float = 0.0
    magic: int = 0
    comment: str = ""
    time: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.ticket <= 0:
            raise ValueError("ticket must be positive")
        # Balance/credit deals legitimately carry an empty symbol.
        if self.volume < 0:
            raise ValueError("volume must be non-negative")
        object.__setattr__(self, "time", _utc(self.time))

    @property
    def net(self) -> float:
        return self.profit + self.commission + self.swap + self.fee


@dataclass(frozen=True, slots=True)
class TradeResult:
    """Closed-trade summary aggregated from deals sharing a position_id."""

    position_id: int
    symbol: str
    volume: float
    profit: float
    commission: float = 0.0
    swap: float = 0.0
    fee: float = 0.0
    deals: int = 0

    @property
    def net(self) -> float:
        return self.profit + self.commission + self.swap + self.fee


@dataclass(frozen=True, slots=True)
class AccountState:
    """Account snapshot enriched with exposure / P&L derived from trading state."""

    account: AccountInfo
    open_positions: int = 0
    pending_orders: int = 0
    exposure_volume: float = 0.0
    net_volume: float = 0.0
    floating_profit: float = 0.0
    day_realized_pnl: float | None = None

    @property
    def balance(self) -> float:
        return self.account.balance

    @property
    def equity(self) -> float:
        return self.account.equity

    @property
    def margin(self) -> float:
        return self.account.margin

    @property
    def free_margin(self) -> float:
        return self.account.free_margin

    @property
    def margin_level(self) -> float | None:
        if self.account.margin > 0:
            return self.account.equity / self.account.margin * 100.0
        return None


__all__ = [
    "AccountState",
    "Deal",
    "Order",
    "Position",
    "PositionSide",
    "TradeResult",
]
