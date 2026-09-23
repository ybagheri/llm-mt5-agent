"""Scoped memory tests: compact writers + retention (no terminal)."""

from __future__ import annotations

from datetime import UTC, datetime

from mt5_agent.domain.execution import ExecutionMode, ExecutionRecord, ExecutionStatus
from mt5_agent.domain.market import Candle, MarketSnapshot, Timeframe
from mt5_agent.domain.memory import MAX_SUMMARY_LEN, MemoryKind
from mt5_agent.domain.planning import TradeAction, TradeProposal
from mt5_agent.domain.strategy import Direction, StrategySignal
from mt5_agent.memory.memories import (
    ShortTermMemory,
    StrategyMemory,
    TradeMemory,
    WorldMemory,
)
from mt5_agent.memory.sqlite_store import SQLiteMemoryStore
from mt5_agent.risk.result import ValidationResult
from mt5_agent.risk.supervisor import SupervisorDecision


def _snapshot() -> MarketSnapshot:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    candle = Candle("EURUSD", Timeframe.M1, now, 1.0, 1.1, 0.9, 1.05)
    tick = None
    return MarketSnapshot("EURUSD", Timeframe.M1, now, candles=(candle,), tick=tick)


def _proposal() -> TradeProposal:
    return TradeProposal(
        TradeAction.BUY,
        "EURUSD",
        0.6,
        "break",
        "donchian",
        entry=1.1,
        stop_loss=1.09,
        take_profit=1.12,
        risk_pct=0.5,
    )


def test_short_term_observation_and_retention() -> None:
    store = SQLiteMemoryStore(":memory:")
    try:
        memory = ShortTermMemory(store, keep_last=3)
        for _ in range(5):
            memory.record_observation(_snapshot())
        assert memory.count() == 3
        (row,) = memory.recent(limit=1)
        assert row.kind == MemoryKind.MARKET_OBSERVATION
        assert "EURUSD" in row.summary
    finally:
        store.close()


def test_trade_memory_writers() -> None:
    store = SQLiteMemoryStore(":memory:")
    try:
        memory = TradeMemory(store)
        assert memory.record_proposal(_proposal()) > 0
        decision = SupervisorDecision(
            True, _proposal(), ValidationResult(True, ()), datetime(2026, 1, 1, tzinfo=UTC)
        )
        memory.record_decision(decision)
        record = ExecutionRecord(
            "c1",
            "EURUSD",
            TradeAction.BUY,
            0.01,
            ExecutionStatus.SUCCESS,
            ExecutionMode.DRY_RUN,
            message="sim",
        )
        memory.record_execution(record)
        memory.record_outcome("EURUSD", "closed +5.0", net=5.0)
        assert memory.count() == 4
        kinds = {row.kind for row in memory.recent(limit=10)}
        assert kinds == {
            MemoryKind.TRADE_PROPOSAL,
            MemoryKind.SUPERVISOR_DECISION,
            MemoryKind.EXECUTION,
            MemoryKind.OUTCOME,
        }
    finally:
        store.close()


def test_strategy_and_world_notes() -> None:
    store = SQLiteMemoryStore(":memory:")
    try:
        strategies = StrategyMemory(store)
        now = datetime(2026, 1, 1, tzinfo=UTC)
        signal = StrategySignal(
            "donchian_breakout",
            "EURUSD",
            Timeframe.M1,
            Direction.LONG,
            0.6,
            (),
            {"a": 1},
            "break",
            now,
        )
        strategies.record_signal(signal)
        strategies.note("EURUSD", "range contraction observed")
        assert strategies.count() == 2
        world = WorldMemory(store)
        world.note("", "equity ATH")
        assert world.count() == 1
    finally:
        store.close()


def test_summaries_stay_compact() -> None:
    store = SQLiteMemoryStore(":memory:")
    try:
        memory = WorldMemory(store)
        memory.note("EURUSD", "x" * 1000)
        (row,) = memory.recent(limit=1)
        assert len(row.summary) <= MAX_SUMMARY_LEN
    finally:
        store.close()
