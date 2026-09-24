"""Strategy domain models (pure, deterministic, LLM-free)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from mt5_agent.domain.market import MarketSnapshot, Timeframe
from mt5_agent.domain.trading import AccountState


class Direction(StrEnum):
    """Signal direction."""

    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class DecisionAction(StrEnum):
    """What the agent should do with a signal (no execution here)."""

    OBSERVE = "OBSERVE"
    CANDIDATE = "CANDIDATE"
    SKIP = "SKIP"


@dataclass(frozen=True, slots=True)
class Setup:
    """Named, testable market setup detected by a strategy."""

    identifier: str
    name: str
    direction: Direction
    confidence: float
    description: str = ""

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("identifier must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be 0..1")


@dataclass(frozen=True, slots=True)
class MarketContext:
    """Everything a strategy may read (snapshot + optional account state)."""

    symbol: str
    timeframe: Timeframe
    snapshot: MarketSnapshot
    account_state: AccountState | None = None
    built_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if self.snapshot.symbol != self.symbol:
            raise ValueError("snapshot.symbol must match context symbol")
        object.__setattr__(self, "built_at", _utc(self.built_at))


@dataclass(frozen=True, slots=True)
class StrategySignal:
    """Deterministic strategy output: objective facts + direction, no LLM."""

    strategy: str
    symbol: str
    timeframe: Timeframe
    direction: Direction
    confidence: float
    setups: tuple[Setup, ...] = ()
    facts: dict[str, object] = field(default_factory=dict)
    rationale: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.strategy.strip():
            raise ValueError("strategy must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be 0..1")
        object.__setattr__(self, "generated_at", _utc(self.generated_at))


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    """Signal triage: observe, consider as candidate, or skip — with reasons."""

    action: DecisionAction
    signal: StrategySignal
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError("reasons must be non-empty")


# Alias kept for the spec's `StrategyContext` naming.
StrategyContext = MarketContext


def select_primary(signals: list[StrategySignal] | tuple[StrategySignal, ...]) -> StrategySignal:
    """Pick the signal the Planner should reason over.

    First directional (LONG/SHORT) signal wins; all-FLAT falls back to the
    first signal (typically the observation-only baseline). Registration order
    is preserved — this only affects *selection*, never evaluation.
    """
    if not signals:
        raise ValueError("at least one signal is required")
    for signal in signals:
        if signal.direction != Direction.FLAT:
            return signal
    return signals[0]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "DecisionAction",
    "Direction",
    "MarketContext",
    "Setup",
    "StrategyContext",
    "StrategyDecision",
    "StrategySignal",
    "select_primary",
]
