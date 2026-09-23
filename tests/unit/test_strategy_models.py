"""Strategy model tests (pure domain)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mt5_agent.domain.market import Candle, MarketSnapshot, Timeframe
from mt5_agent.domain.strategy import (
    DecisionAction,
    Direction,
    MarketContext,
    Setup,
    StrategyDecision,
    StrategySignal,
)


def _candle(close: float, **kwargs: object) -> Candle:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    base: dict[str, object] = {
        "symbol": "EURUSD",
        "timeframe": Timeframe.M1,
        "time": now,
        "open": 1.0,
        "high": 1.2,
        "low": 0.9,
        "close": close,
    }
    base.update(kwargs)
    return Candle(**base)  # type: ignore[arg-type]


def _context(n: int = 5) -> MarketContext:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    candles = tuple(_candle(1.0 + i * 0.001) for i in range(n))
    snap = MarketSnapshot("EURUSD", Timeframe.M1, now, candles=candles)
    return MarketContext("EURUSD", Timeframe.M1, snap)


def test_setup_validation() -> None:
    with pytest.raises(ValueError):
        Setup("  ", "x", Direction.LONG, 0.5)
    with pytest.raises(ValueError):
        Setup("a", "x", Direction.LONG, 1.5)


def test_context_symbol_mismatch() -> None:
    ctx = _context()
    with pytest.raises(ValueError):
        MarketContext("XAUUSD", Timeframe.M1, ctx.snapshot)


def test_signal_confidence_bounds() -> None:
    with pytest.raises(ValueError):
        StrategySignal("s", "EURUSD", Timeframe.M1, Direction.FLAT, 2.0)
    sig = StrategySignal("s", "EURUSD", Timeframe.M1, Direction.FLAT, 0.0)
    assert sig.setups == ()


def test_decision_requires_reasons() -> None:
    sig = StrategySignal("s", "EURUSD", Timeframe.M1, Direction.FLAT, 0.0)
    with pytest.raises(ValueError):
        StrategyDecision(DecisionAction.SKIP, sig, ())
    assert StrategyDecision(DecisionAction.SKIP, sig, ("r",)).action == DecisionAction.SKIP
