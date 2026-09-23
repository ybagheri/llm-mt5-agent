"""Supervisor: the safety boundary between Planner and Executor.

`check()` is pure (no side effects); `review()` records the verdict into an
in-memory ledger that powers duplicate + cooldown rules. The ledger is
process-local in Phase 07 (Phase 09 persists decisions to memory).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from mt5_agent.domain.planning import TradeAction, TradeProposal
from mt5_agent.risk.config import RiskConfig
from mt5_agent.risk.context import DecisionRecord, RiskContext
from mt5_agent.risk.engine import RiskEngine
from mt5_agent.risk.result import ValidationResult
from mt5_agent.risk.rules import RiskRule


@dataclass(frozen=True, slots=True)
class SupervisorDecision:
    """Immutable review outcome (auditable)."""

    approved: bool
    proposal: TradeProposal
    result: ValidationResult
    decided_at: datetime

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(v.code.value for v in self.result.violations)


class Supervisor:
    """Reviews proposals; can reject anything the LLM produces."""

    def __init__(
        self,
        engine: RiskEngine | None = None,
        config: RiskConfig | None = None,
        rules: tuple[RiskRule, ...] | None = None,
    ) -> None:
        self._engine = engine or RiskEngine(config, rules)
        self._ledger: list[DecisionRecord] = []

    @property
    def engine(self) -> RiskEngine:
        return self._engine

    @property
    def ledger(self) -> tuple[DecisionRecord, ...]:
        return tuple(self._ledger)

    def check(
        self,
        proposal: TradeProposal,
        context: RiskContext,
        *,
        now: datetime | None = None,
    ) -> ValidationResult:
        """Pure validation (ledger untouched)."""
        return self._engine.validate(proposal, self._with_history(context), now=now)

    def review(
        self,
        proposal: TradeProposal,
        context: RiskContext,
        *,
        now: datetime | None = None,
    ) -> SupervisorDecision:
        """Validate and record the verdict (HOLD verdicts are not recorded)."""
        decided_at = now or datetime.now(UTC)
        result = self._engine.validate(proposal, self._with_history(context), now=decided_at)
        if proposal.action != TradeAction.HOLD:
            self._ledger.append(
                DecisionRecord(proposal.symbol, proposal.action.value, result.approved, decided_at)
            )
        return SupervisorDecision(result.approved, proposal, result, decided_at)

    def _with_history(self, context: RiskContext) -> RiskContext:
        if not self._ledger:
            return context
        merged = tuple(context.recent_decisions) + tuple(self._ledger)
        return RiskContext(
            account=context.account,
            positions=context.positions,
            orders=context.orders,
            spreads_points=dict(context.spreads_points),
            symbol_points=dict(context.symbol_points),
            server_time=context.server_time,
            day_pnl=context.day_pnl,
            recent_decisions=merged,
        )


__all__ = ["Supervisor", "SupervisorDecision"]
