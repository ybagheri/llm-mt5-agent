"""Memory store tests (SQLite on :memory: + tmp files; no terminal)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mt5_agent.domain.memory import MemoryKind, MemoryRecord, MemoryScope
from mt5_agent.memory.sqlite_store import SQLiteMemoryStore


def _record(scope: MemoryScope = MemoryScope.TRADE, **kwargs: object) -> MemoryRecord:
    base: dict[str, object] = {
        "scope": scope,
        "kind": MemoryKind.TRADE_PROPOSAL,
        "summary": "BUY EURUSD",
        "symbol": "EURUSD",
    }
    base.update(kwargs)
    return MemoryRecord(**base)  # type: ignore[arg-type]


def test_append_recent_count() -> None:
    store = SQLiteMemoryStore(":memory:")
    try:
        assert store.count(MemoryScope.TRADE) == 0
        row_id = store.append(_record())
        assert row_id > 0
        rows = store.recent(MemoryScope.TRADE)
        assert len(rows) == 1
        assert rows[0].record_id == row_id
        assert rows[0].symbol == "EURUSD"
    finally:
        store.close()


def test_filters_and_order() -> None:
    store = SQLiteMemoryStore(":memory:")
    try:
        store.append(_record(symbol="EURUSD"))
        store.append(_record(symbol="XAUUSD"))
        store.append(_record(kind=MemoryKind.EXECUTION, symbol="EURUSD", summary="fill"))
        assert len(store.recent(MemoryScope.TRADE, symbol="EURUSD")) == 2
        assert len(store.recent(MemoryScope.TRADE, kind=MemoryKind.EXECUTION)) == 1
        rows = store.recent(MemoryScope.TRADE, limit=1)
        assert rows[0].summary == "fill"  # newest first
        since = datetime.now(UTC) + timedelta(seconds=1)
        assert store.recent(MemoryScope.TRADE, since=since) == []
        with pytest.raises(ValueError):
            store.recent(MemoryScope.TRADE, limit=0)
    finally:
        store.close()


def test_prune_keeps_newest() -> None:
    store = SQLiteMemoryStore(":memory:")
    try:
        for i in range(5):
            store.append(_record(summary=f"row {i}"))
        removed = store.prune(MemoryScope.TRADE, keep_last=2)
        assert removed == 3
        assert store.count(MemoryScope.TRADE) == 2
        assert store.recent(MemoryScope.TRADE, limit=5)[0].summary == "row 4"
        with pytest.raises(ValueError):
            store.prune(MemoryScope.TRADE, keep_last=-1)
    finally:
        store.close()


def test_persistence_across_reopen(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = tmp_path / "memory.db"
    store = SQLiteMemoryStore(db)
    store.append(_record(summary="persist me"))
    store.close()
    reopened = SQLiteMemoryStore(db)
    try:
        assert reopened.recent(MemoryScope.TRADE)[0].summary == "persist me"
    finally:
        reopened.close()


def test_record_validation() -> None:
    with pytest.raises(ValueError):
        MemoryRecord(MemoryScope.TRADE, MemoryKind.TRADE_PROPOSAL, "  ")
    with pytest.raises(ValueError):
        MemoryRecord(MemoryScope.TRADE, MemoryKind.TRADE_PROPOSAL, "x" * 281)
    assert MemoryKind.TRADE_PROPOSAL.scope() == MemoryScope.TRADE
    assert MemoryKind.MARKET_OBSERVATION.scope() == MemoryScope.SHORT_TERM
    assert MemoryKind.STRATEGY_NOTE.scope() == MemoryScope.STRATEGY
    assert MemoryKind.WORLD_NOTE.scope() == MemoryScope.WORLD
