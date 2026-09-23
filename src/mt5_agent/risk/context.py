"""Risk evaluation context: everything rules may read (all explicit)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from mt5_agent.domain.trading import AccountState, Order, Position


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    """Past supervisor verdict (powers duplicate + cooldown rules)."""

    symbol: str
    action: str
    approved: bool
    at: datetime


@dataclass(frozen=True, slots=True)
class RiskContext:
    """Snapshot for rule evaluation. Spreads/points keyed by symbol."""

    account: AccountState
    positions: tuple[Position, ...] = ()
    orders: tuple[Order, ...] = ()
    spreads_points: Mapping[str, float] = field(default_factory=dict)
    symbol_points: Mapping[str, float] = field(default_factory=dict)
    server_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    day_pnl: float | None = None
    recent_decisions: tuple[DecisionRecord, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "server_time", _utc(self.server_time))


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = ["DecisionRecord", "RiskContext"]
