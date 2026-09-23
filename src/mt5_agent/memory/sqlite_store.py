"""SQLite-backed `MemoryStore` (stdlib `sqlite3`, thread-safe, WAL)."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mt5_agent.domain.memory import MemoryKind, MemoryRecord, MemoryScope
from mt5_agent.memory.store import MemoryStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    kind TEXT NOT NULL,
    symbol TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_scope_id ON memory_records (scope, id DESC);
CREATE INDEX IF NOT EXISTS idx_memory_symbol ON memory_records (symbol);
"""


class SQLiteMemoryStore(MemoryStore):
    """File-backed store. `:memory:` supported for tests."""

    def __init__(self, path: str | Path = "data/memory.db") -> None:
        self._path = str(path)
        self._lock = threading.Lock()
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    @property
    def path(self) -> str:
        return self._path

    def append(self, record: MemoryRecord) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO memory_records (scope, kind, symbol, summary, data, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.scope.value,
                    record.kind.value,
                    record.symbol,
                    record.summary,
                    json.dumps(record.data, default=str),
                    record.created_at.isoformat(),
                ),
            )
            self._conn.commit()
            return int(cursor.lastrowid or 0)

    def recent(
        self,
        scope: MemoryScope,
        *,
        limit: int = 20,
        symbol: str | None = None,
        kind: MemoryKind | None = None,
        since: datetime | None = None,
    ) -> list[MemoryRecord]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        query = "SELECT id, scope, kind, symbol, summary, data, created_at FROM memory_records"
        clauses = ["scope = ?"]
        params: list[Any] = [scope.value]
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind.value)
        if since is not None:
            clauses.append("created_at >= ?")
            params.append(since.isoformat())
        query += " WHERE " + " AND ".join(clauses) + " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [_row_to_record(row) for row in rows]

    def count(self, scope: MemoryScope) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM memory_records WHERE scope = ?", (scope.value,)
            ).fetchone()
        return int(row[0] if row else 0)

    def prune(self, scope: MemoryScope, keep_last: int) -> int:
        if keep_last < 0:
            raise ValueError("keep_last must be >= 0")
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM memory_records WHERE scope = ? AND id NOT IN "
                "(SELECT id FROM memory_records WHERE scope = ? ORDER BY id DESC LIMIT ?)",
                (scope.value, scope.value, keep_last),
            )
            self._conn.commit()
            return int(cursor.rowcount or 0)

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def _row_to_record(row: tuple[Any, ...]) -> MemoryRecord:
    record_id, scope, kind, symbol, summary, data, created_at = row
    try:
        payload = json.loads(data) if data else {}
    except json.JSONDecodeError:
        payload = {}
    try:
        at = datetime.fromisoformat(str(created_at))
    except ValueError:
        at = datetime.now(UTC)
    return MemoryRecord(
        MemoryScope(str(scope)),
        MemoryKind(str(kind)),
        str(summary),
        symbol=str(symbol or ""),
        data=payload if isinstance(payload, dict) else {},
        created_at=at,
        record_id=int(record_id),
    )


__all__ = ["SQLiteMemoryStore"]
