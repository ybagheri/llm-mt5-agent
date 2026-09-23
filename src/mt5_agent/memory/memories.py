"""Scoped memory facades: compact writers + bounded readers over a `MemoryStore`.

Each facade owns one scope and enforces retention on every append, so memory
stays a rolling window of structured rows — never a transcript dump.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from mt5_agent.domain.execution import ExecutionRecord
from mt5_agent.domain.market import MarketSnapshot
from mt5_agent.domain.memory import MAX_SUMMARY_LEN, MemoryKind, MemoryRecord, MemoryScope
from mt5_agent.domain.planning import TradeProposal
from mt5_agent.domain.strategy import StrategySignal
from mt5_agent.memory.store import MemoryStore
from mt5_agent.risk.supervisor import SupervisorDecision


def _clip(text: str, limit: int = MAX_SUMMARY_LEN) -> str:
    text = " ".join(text.split())
    return text[:limit] if len(text) <= limit else text[: limit - 1] + "…"


class _ScopedMemory:
    scope: MemoryScope = MemoryScope.SHORT_TERM
    keep_last: int = 100

    def __init__(self, store: MemoryStore, *, keep_last: int | None = None) -> None:
        self._store = store
        if keep_last is not None:
            if keep_last < 1:
                raise ValueError("keep_last must be >= 1")
            self.keep_last = keep_last

    def _append(
        self,
        kind: MemoryKind,
        summary: str,
        symbol: str = "",
        data: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> int:
        record = MemoryRecord(
            self.scope,
            kind,
            _clip(summary),
            symbol=symbol,
            data=data or {},
            created_at=created_at or datetime.now(UTC),
        )
        row_id = self._store.append(record)
        self._store.prune(self.scope, self.keep_last)
        return row_id

    def recent(self, limit: int = 20, **filters: Any) -> list[MemoryRecord]:
        return self._store.recent(self.scope, limit=limit, **filters)

    def count(self) -> int:
        return self._store.count(self.scope)


class ShortTermMemory(_ScopedMemory):
    """Rolling market observations (default keeps last 100)."""

    scope = MemoryScope.SHORT_TERM
    keep_last = 100

    def record_observation(self, snapshot: MarketSnapshot) -> int:
        return self._append(
            MemoryKind.MARKET_OBSERVATION,
            f"{snapshot.symbol} {snapshot.timeframe.value}: close {snapshot.latest_close}",
            symbol=snapshot.symbol,
            data={
                "timeframe": snapshot.timeframe.value,
                "candles": len(snapshot.candles),
                "latest_close": snapshot.latest_close,
                "bid": snapshot.tick.bid if snapshot.tick else None,
                "ask": snapshot.tick.ask if snapshot.tick else None,
            },
        )


class TradeMemory(_ScopedMemory):
    """Proposals, verdicts, executions, outcomes (default keeps last 500)."""

    scope = MemoryScope.TRADE
    keep_last = 500

    def record_proposal(self, proposal: TradeProposal) -> int:
        return self._append(
            MemoryKind.TRADE_PROPOSAL,
            f"{proposal.action.value} {proposal.symbol} conf={proposal.confidence:.2f}",
            symbol=proposal.symbol,
            data={
                "action": proposal.action.value,
                "entry": proposal.entry,
                "stop_loss": proposal.stop_loss,
                "take_profit": proposal.take_profit,
                "risk_pct": proposal.risk_pct,
                "confidence": proposal.confidence,
                "strategy": proposal.strategy,
                "setup_id": proposal.setup_id,
            },
        )

    def record_decision(self, decision: SupervisorDecision) -> int:
        proposal = decision.proposal
        return self._append(
            MemoryKind.SUPERVISOR_DECISION,
            f"{'APPROVED' if decision.approved else 'REJECTED'} "
            f"{proposal.action.value} {proposal.symbol} [{','.join(decision.codes) or 'ok'}]",
            symbol=proposal.symbol,
            data={
                "approved": decision.approved,
                "codes": list(decision.codes),
                "action": proposal.action.value,
            },
        )

    def record_execution(self, record: ExecutionRecord) -> int:
        return self._append(
            MemoryKind.EXECUTION,
            f"{record.status.value} {record.action.value} {record.symbol} "
            f"{record.volume} ticket={record.ticket}",
            symbol=record.symbol,
            data={
                "status": record.status.value,
                "mode": record.mode.value,
                "ticket": record.ticket,
                "deal": record.deal,
                "executed_price": record.executed_price,
                "slippage": record.slippage,
                "error_code": record.error_code,
            },
        )

    def record_outcome(self, symbol: str, summary: str, **fields: Any) -> int:
        return self._append(MemoryKind.OUTCOME, summary, symbol=symbol, data=fields)


class WorldMemory(_ScopedMemory):
    """Account/session regime notes (default keeps last 200)."""

    scope = MemoryScope.WORLD
    keep_last = 200

    def note(self, symbol: str, summary: str, **fields: Any) -> int:
        return self._append(MemoryKind.WORLD_NOTE, summary, symbol=symbol, data=fields)


class StrategyMemory(_ScopedMemory):
    """Signals + analyst notes (default keeps last 200)."""

    scope = MemoryScope.STRATEGY
    keep_last = 200

    def record_signal(self, signal: StrategySignal) -> int:
        return self._append(
            MemoryKind.STRATEGY_SIGNAL,
            f"{signal.strategy}:{signal.direction.value} {signal.symbol} "
            f"conf={signal.confidence:.2f}",
            symbol=signal.symbol,
            data={
                "strategy": signal.strategy,
                "direction": signal.direction.value,
                "confidence": signal.confidence,
                "setups": [s.identifier for s in signal.setups],
                "facts": {k: signal.facts[k] for k in list(signal.facts)[:12]},
            },
        )

    def note(self, symbol: str, summary: str, **fields: Any) -> int:
        return self._append(MemoryKind.STRATEGY_NOTE, summary, symbol=symbol, data=fields)


__all__ = ["ShortTermMemory", "StrategyMemory", "TradeMemory", "WorldMemory"]
