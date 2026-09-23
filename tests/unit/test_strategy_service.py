"""StrategyService tests (fake strategies, triage rules)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mt5_agent.application.strategy_service import StrategyService, triage
from mt5_agent.domain.market import Candle, MarketSnapshot, Timeframe
from mt5_agent.domain.strategy import (
    DecisionAction,
    Direction,
    MarketContext,
    Setup,
    StrategySignal,
)
from mt5_agent.strategies.base import Strategy
from mt5_agent.strategies.null_strategy import NullStrategy


def _context() -> MarketContext:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    candle = Candle("EURUSD", Timeframe.M1, now, 1.0, 1.1, 0.9, 1.05)
    snap = MarketSnapshot("EURUSD", Timeframe.M1, now, candles=(candle,))
    return MarketContext("EURUSD", Timeframe.M1, snap)


class LongStrategy(Strategy):
    name = "long"

    def analyze(self, context: MarketContext) -> StrategySignal:
        now = datetime.now(UTC)
        setup = Setup("long:1", "LongSetup", Direction.LONG, 0.8)
        return StrategySignal(
            "long",
            context.symbol,
            context.timeframe,
            Direction.LONG,
            0.8,
            (setup,),
            {},
            "long",
            now,
        )


class BoomStrategy(Strategy):
    name = "boom"

    def analyze(self, context: MarketContext) -> StrategySignal:
        raise RuntimeError("boom")


def test_service_runs_all() -> None:
    svc = StrategyService([NullStrategy(), LongStrategy()])
    signals = svc.analyze(_context())
    assert [s.strategy for s in signals] == ["null", "long"]
    decisions = svc.decide(_context())
    assert [d.action for d in decisions] == [DecisionAction.SKIP, DecisionAction.CANDIDATE]


def test_failing_strategy_degrades_to_flat() -> None:
    svc = StrategyService([BoomStrategy()])
    (signal,) = svc.analyze(_context())
    assert signal.direction == Direction.FLAT
    assert "boom" in str(signal.facts.get("error", "")).lower()


def test_service_requires_strategies() -> None:
    with pytest.raises(ValueError):
        StrategyService([])


def test_triage_flat_with_setups_observes() -> None:
    now = datetime.now(UTC)
    setup = Setup("s:1", "S", Direction.FLAT, 0.3)
    sig = StrategySignal("s", "EURUSD", Timeframe.M1, Direction.FLAT, 0.0, (setup,), {}, "", now)
    assert triage(sig).action == DecisionAction.OBSERVE
