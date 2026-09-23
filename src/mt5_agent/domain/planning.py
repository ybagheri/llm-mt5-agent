"""Planning domain models: planner input + trade proposals (no LLM deps)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from mt5_agent.domain.market import MarketSnapshot, Timeframe
from mt5_agent.domain.strategy import StrategySignal
from mt5_agent.domain.trading import AccountState, Position


class TradeAction(StrEnum):
    """Proposed action. HOLD means 'do nothing' (always safe)."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True, slots=True)
class MemoryNote:
    """Minimal memory excerpt for planner context (Phase 09 will formalize)."""

    kind: str
    text: str

    def __post_init__(self) -> None:
        if not self.kind.strip() or not self.text.strip():
            raise ValueError("kind and text must be non-empty")


@dataclass(frozen=True, slots=True)
class PlannerInput:
    """Structured context the Planner reasons over (never raw MT5 objects)."""

    symbol: str
    timeframe: Timeframe
    snapshot: MarketSnapshot
    signal: StrategySignal
    account: AccountState | None = None
    open_positions: tuple[Position, ...] = ()
    memory: tuple[MemoryNote, ...] = ()

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if self.snapshot.symbol != self.symbol:
            raise ValueError("snapshot.symbol must match input symbol")
        if self.signal.symbol != self.symbol:
            raise ValueError("signal.symbol must match input symbol")
        for position in self.open_positions:
            if position.symbol != self.symbol:
                raise ValueError("open_positions must match input symbol")


@dataclass(frozen=True, slots=True)
class TradeProposal:
    """Structured trade proposal. Advisory only — Supervisor decides (Phase 07)."""

    action: TradeAction
    symbol: str
    confidence: float
    rationale: str
    strategy: str
    setup_id: str = ""
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_pct: float = 0.0
    volume: float | None = None
    provider: str = ""
    model: str = ""
    latency_ms: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be 0..1")
        if not self.rationale.strip():
            raise ValueError("rationale must be non-empty")
        if not 0.0 <= self.risk_pct <= 100.0:
            raise ValueError("risk_pct must be 0..100")
        if self.volume is not None and self.volume <= 0:
            raise ValueError("volume must be positive when set")
        for price in (self.entry, self.stop_loss, self.take_profit):
            if price is not None and price <= 0:
                raise ValueError("prices must be positive when set")
        if self.action == TradeAction.HOLD:
            if self.entry is not None or self.volume is not None:
                raise ValueError("HOLD proposals carry no entry/volume")
        object.__setattr__(self, "created_at", _utc(self.created_at))

    @property
    def is_actionable(self) -> bool:
        return self.action in (TradeAction.BUY, TradeAction.SELL)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = ["MemoryNote", "PlannerInput", "TradeAction", "TradeProposal"]
