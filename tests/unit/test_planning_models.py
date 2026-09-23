"""Planning model tests (validation only)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mt5_agent.domain.market import Candle, MarketSnapshot, Timeframe
from mt5_agent.domain.planning import MemoryNote, PlannerInput, TradeAction, TradeProposal
from mt5_agent.domain.strategy import Direction, StrategySignal


def _signal(symbol: str = "EURUSD") -> StrategySignal:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return StrategySignal(
        "donchian_breakout", symbol, Timeframe.M1, Direction.LONG, 0.6, (), {"k": 1}, "break", now
    )


def _snapshot(symbol: str = "EURUSD") -> MarketSnapshot:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    candle = Candle(symbol, Timeframe.M1, now, 1.0, 1.1, 0.9, 1.05)
    return MarketSnapshot(symbol, Timeframe.M1, now, candles=(candle,))


def _input(symbol: str = "EURUSD") -> PlannerInput:
    return PlannerInput(symbol, Timeframe.M1, _snapshot(symbol), _signal(symbol))


def test_proposal_validation() -> None:
    with pytest.raises(ValueError):
        TradeProposal(TradeAction.BUY, "EURUSD", 0.5, "", "s")
    with pytest.raises(ValueError):
        TradeProposal(TradeAction.BUY, "EURUSD", 1.5, "r", "s")
    with pytest.raises(ValueError):
        TradeProposal(TradeAction.HOLD, "EURUSD", 0.0, "r", "s", entry=1.1)
    hold = TradeProposal(TradeAction.HOLD, "EURUSD", 0.0, "wait", "s")
    assert hold.is_actionable is False
    buy = TradeProposal(
        TradeAction.BUY, "EURUSD", 0.7, "break", "s", entry=1.1, stop_loss=1.0, take_profit=1.2
    )
    assert buy.is_actionable is True


def test_input_symbol_consistency() -> None:
    with pytest.raises(ValueError):
        PlannerInput("XAUUSD", Timeframe.M1, _snapshot("EURUSD"), _signal("EURUSD"))
    with pytest.raises(ValueError):
        PlannerInput("EURUSD", Timeframe.M1, _snapshot(), _signal("XAUUSD"))
    assert _input().open_positions == ()


def test_memory_note_validation() -> None:
    with pytest.raises(ValueError):
        MemoryNote("  ", "text")
    assert MemoryNote("decision", "held overnight").kind == "decision"
