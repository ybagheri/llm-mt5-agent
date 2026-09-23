"""NullStrategy: observation-only baseline (always FLAT)."""

from __future__ import annotations

from datetime import UTC, datetime

from mt5_agent.domain.strategy import (
    Direction,
    MarketContext,
    StrategySignal,
)
from mt5_agent.strategies.base import Strategy


class NullStrategy(Strategy):
    """Safe default: observes, never suggests direction."""

    name = "null"

    def analyze(self, context: MarketContext) -> StrategySignal:
        candles = context.snapshot.candles
        return StrategySignal(
            strategy=self.name,
            symbol=context.symbol,
            timeframe=context.timeframe,
            direction=Direction.FLAT,
            confidence=0.0,
            setups=(),
            facts={
                "candles": len(candles),
                "latest_close": candles[-1].close if candles else None,
                "mode": "observation-only",
            },
            rationale="NullStrategy is observation-only and never emits direction.",
            generated_at=datetime.now(UTC),
        )


__all__ = ["NullStrategy"]
