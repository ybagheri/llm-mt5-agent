"""Memory domain models: compact structured records (no storage deps)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class MemoryScope(StrEnum):
    """Four scopes; facades own one each."""

    SHORT_TERM = "short_term"
    TRADE = "trade"
    WORLD = "world"
    STRATEGY = "strategy"


class MemoryKind(StrEnum):
    """Compact record kinds (never free-form transcripts)."""

    MARKET_OBSERVATION = "market_observation"
    STRATEGY_SIGNAL = "strategy_signal"
    TRADE_PROPOSAL = "trade_proposal"
    SUPERVISOR_DECISION = "supervisor_decision"
    EXECUTION = "execution"
    OUTCOME = "outcome"
    STRATEGY_NOTE = "strategy_note"
    WORLD_NOTE = "world_note"

    def scope(self) -> MemoryScope:
        if self in (
            MemoryKind.TRADE_PROPOSAL,
            MemoryKind.SUPERVISOR_DECISION,
            MemoryKind.EXECUTION,
            MemoryKind.OUTCOME,
        ):
            return MemoryScope.TRADE
        if self == MemoryKind.MARKET_OBSERVATION:
            return MemoryScope.SHORT_TERM
        if self == MemoryKind.STRATEGY_SIGNAL or self == MemoryKind.STRATEGY_NOTE:
            return MemoryScope.STRATEGY
        return MemoryScope.WORLD


MAX_SUMMARY_LEN = 280


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """One compact row. `summary` is capped; `data` holds whitelisted fields only."""

    scope: MemoryScope
    kind: MemoryKind
    summary: str
    symbol: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    record_id: int | None = None

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("summary must be non-empty")
        if len(self.summary) > MAX_SUMMARY_LEN:
            raise ValueError(f"summary exceeds {MAX_SUMMARY_LEN} chars (keep records compact)")
        object.__setattr__(self, "created_at", _utc(self.created_at))


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = ["MAX_SUMMARY_LEN", "MemoryKind", "MemoryRecord", "MemoryScope"]
