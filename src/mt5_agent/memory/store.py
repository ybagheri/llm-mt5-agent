"""Memory store interface (SQLite today, PostgreSQL later — same contract)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from mt5_agent.domain.memory import MemoryKind, MemoryRecord, MemoryScope


class MemoryStore(ABC):
    """Append-only record store with scoped queries and retention pruning."""

    @abstractmethod
    def append(self, record: MemoryRecord) -> int:
        """Persist one record; returns its row id."""
        ...

    @abstractmethod
    def recent(
        self,
        scope: MemoryScope,
        *,
        limit: int = 20,
        symbol: str | None = None,
        kind: MemoryKind | None = None,
        since: datetime | None = None,
    ) -> list[MemoryRecord]:
        """Newest-first rows for a scope with optional filters."""
        ...

    @abstractmethod
    def count(self, scope: MemoryScope) -> int:
        """Row count for a scope."""
        ...

    @abstractmethod
    def prune(self, scope: MemoryScope, keep_last: int) -> int:
        """Delete oldest rows beyond `keep_last`; returns rows removed."""
        ...

    def close(self) -> None:
        """Release resources (default: no-op)."""
        return None


__all__ = ["MemoryStore"]
