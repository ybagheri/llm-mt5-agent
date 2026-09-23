"""Measured-move abstraction: impulse + structure-break detection.

Extensible design: `MeasureMoveStrategy` implements the deterministic pipeline
(range measurement -> Donchian structure break -> setups/signal) while subclasses
override hooks (`confirm`, `confidence_of`, `setup_for`) to specialize behavior
without rewriting the engine. The default concrete subclass,
`DonchianBreakoutStrategy`, is a pure N-bar-breakout reader.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from datetime import UTC, datetime

from mt5_agent.domain.market import Candle
from mt5_agent.domain.strategy import (
    Direction,
    MarketContext,
    Setup,
    StrategySignal,
)
from mt5_agent.strategies.base import Strategy


@dataclass(frozen=True, slots=True)
class MeasureMoveParams:
    """Tunable, serializable parameters (no magic numbers in code)."""

    lookback: int = 20
    min_candles: int = 5
    breakout_confidence: float = 0.6

    def __post_init__(self) -> None:
        if self.lookback < 2:
            raise ValueError("lookback must be >= 2")
        if self.min_candles < 1:
            raise ValueError("min_candles must be >= 1")
        if not 0.0 <= self.breakout_confidence <= 1.0:
            raise ValueError("breakout_confidence must be 0..1")


class MeasureMoveStrategy(Strategy, ABC):
    """Base class: override hooks, inherit the pipeline."""

    name = "measure_move"

    def __init__(self, params: MeasureMoveParams | None = None) -> None:
        self._params = params or MeasureMoveParams()

    @property
    def params(self) -> MeasureMoveParams:
        return self._params

    # -- pipeline ------------------------------------------------------
    def analyze(self, context: MarketContext) -> StrategySignal:
        candles = list(context.snapshot.candles)
        facts: dict[str, object] = {
            "candles": len(candles),
            "lookback": self._params.lookback,
        }
        if len(candles) < self._params.min_candles:
            return self._signal(
                context,
                Direction.FLAT,
                0.0,
                (),
                facts | {"skip": f"need >= {self._params.min_candles} candles"},
                "Insufficient data: observation only.",
            )
        window = candles[-self._params.lookback :] if len(candles) >= 2 else candles
        prior = window[:-1]
        latest = window[-1]
        hi = max(c.high for c in prior)
        lo = min(c.low for c in prior)
        move = hi - lo
        facts |= {
            "window": len(window),
            "prior_high": hi,
            "prior_low": lo,
            "impulse_range": move,
            "latest_close": latest.close,
            "latest_high": latest.high,
            "latest_low": latest.low,
        }
        direction = Direction.FLAT
        if latest.close > hi:
            direction = Direction.LONG
        elif latest.close < lo:
            direction = Direction.SHORT
        if direction == Direction.FLAT:
            return self._signal(
                context,
                direction,
                0.0,
                (),
                facts | {"skip": "no structure break"},
                "No N-bar structure break: observation only.",
            )
        if not self.confirm(latest, window, direction):
            return self._signal(
                context,
                Direction.FLAT,
                0.0,
                (),
                facts | {"skip": "unconfirmed"},
                "Breakout rejected by confirm() hook: observation only.",
            )
        setup = self.setup_for(direction, latest, facts)
        confidence = self.confidence_of(direction, latest, facts)
        return self._signal(
            context,
            direction,
            confidence,
            (setup,),
            facts,
            f"{setup.name}: close {latest.close} broke prior "
            f"{'high' if direction == Direction.LONG else 'low'}.",
        )

    # -- hooks (override to specialize) ---------------------------------
    def confirm(self, latest: Candle, window: list[Candle], direction: Direction) -> bool:
        """Veto hook. Default: accept every structure break."""
        return True

    def confidence_of(
        self, direction: Direction, latest: Candle, facts: dict[str, object]
    ) -> float:
        """Confidence hook. Default: fixed param value."""
        return self._params.breakout_confidence

    def setup_for(self, direction: Direction, latest: Candle, facts: dict[str, object]) -> Setup:
        """Setup-naming hook. Default: generic breakout setup."""
        return Setup(
            identifier=f"{self.name}:breakout:{direction.value.lower()}",
            name="StructureBreakout",
            direction=direction,
            confidence=self._params.breakout_confidence,
            description=f"N-bar close break ({direction.value}).",
        )

    # -- helpers ----------------------------------------------------------
    def _signal(
        self,
        context: MarketContext,
        direction: Direction,
        confidence: float,
        setups: tuple[Setup, ...],
        facts: dict[str, object],
        rationale: str,
    ) -> StrategySignal:
        return StrategySignal(
            strategy=self.name,
            symbol=context.symbol,
            timeframe=context.timeframe,
            direction=direction,
            confidence=confidence,
            setups=setups,
            facts=facts,
            rationale=rationale,
            generated_at=datetime.now(UTC),
        )


class DonchianBreakoutStrategy(MeasureMoveStrategy):
    """Concrete N-bar breakout reader (pure Donchian structure break)."""

    name = "donchian_breakout"


__all__ = [
    "DonchianBreakoutStrategy",
    "MeasureMoveParams",
    "MeasureMoveStrategy",
]
