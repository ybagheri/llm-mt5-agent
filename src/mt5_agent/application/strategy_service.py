"""Strategy service: run registered strategies over a MarketContext."""

from __future__ import annotations

from mt5_agent.domain.strategy import (
    DecisionAction,
    Direction,
    MarketContext,
    StrategyDecision,
    StrategySignal,
)
from mt5_agent.strategies.base import Strategy


class StrategyService:
    """Orchestrates deterministic strategies + triages signals into decisions."""

    def __init__(self, strategies: list[Strategy]) -> None:
        if not strategies:
            raise ValueError("at least one strategy is required")
        self._strategies = list(strategies)

    @property
    def strategies(self) -> list[Strategy]:
        return list(self._strategies)

    def analyze(self, context: MarketContext) -> list[StrategySignal]:
        """Run every strategy; a failing strategy yields a FLAT error signal."""
        signals: list[StrategySignal] = []
        for strategy in self._strategies:
            try:
                signals.append(strategy.analyze(context))
            except Exception as exc:
                signals.append(_error_signal(strategy, context, exc))
        return signals

    def decide(self, context: MarketContext) -> list[StrategyDecision]:
        """Triage signals: FLAT -> OBSERVE/SKIP, directional -> CANDIDATE."""
        return [triage(signal) for signal in self.analyze(context)]


def triage(signal: StrategySignal) -> StrategyDecision:
    """Pure triage rule (deterministic, no LLM)."""
    if signal.direction == Direction.FLAT:
        if signal.setups:
            return StrategyDecision(DecisionAction.OBSERVE, signal, ("flat with setups",))
        return StrategyDecision(DecisionAction.SKIP, signal, ("no direction",))
    return StrategyDecision(DecisionAction.CANDIDATE, signal, (f"{signal.direction.value} setup",))


def _error_signal(strategy: Strategy, context: MarketContext, exc: Exception) -> StrategySignal:
    from datetime import UTC, datetime

    return StrategySignal(
        strategy=getattr(strategy, "name", type(strategy).__name__),
        symbol=context.symbol,
        timeframe=context.timeframe,
        direction=Direction.FLAT,
        confidence=0.0,
        setups=(),
        facts={"error": f"{type(exc).__name__}: {exc}"},
        rationale="Strategy raised; degraded to FLAT (fail safely).",
        generated_at=datetime.now(UTC),
    )


__all__ = ["StrategyService", "triage"]
