"""Risk engine: runs every rule, approves only when all pass (no patch-ups)."""

from __future__ import annotations

from datetime import UTC, datetime

from mt5_agent.domain.planning import TradeAction, TradeProposal
from mt5_agent.risk.config import RiskConfig
from mt5_agent.risk.context import RiskContext
from mt5_agent.risk.result import ValidationResult, Violation
from mt5_agent.risk.rules import DEFAULT_RULES, RiskRule


class RiskEngine:
    """Deterministic validator. HOLD proposals pass trivially (no-op)."""

    def __init__(
        self,
        config: RiskConfig | None = None,
        rules: tuple[RiskRule, ...] | None = None,
    ) -> None:
        self._config = config or RiskConfig()
        self._rules = rules if rules is not None else DEFAULT_RULES

    @property
    def config(self) -> RiskConfig:
        return self._config

    @property
    def rules(self) -> tuple[RiskRule, ...]:
        return self._rules

    def validate(
        self,
        proposal: TradeProposal,
        context: RiskContext,
        *,
        now: datetime | None = None,
    ) -> ValidationResult:
        """Evaluate all rules; never modifies the proposal (reject > correct)."""
        checked_at = now or datetime.now(UTC)
        if proposal.action == TradeAction.HOLD:
            return ValidationResult(True, (), checked_at)
        violations: list[Violation] = []
        for rule in self._rules:
            violation = rule.check(proposal, context, self._config)
            if violation is not None:
                violations.append(violation)
        if violations:
            return ValidationResult(False, tuple(violations), checked_at)
        return ValidationResult(True, (), checked_at)


__all__ = ["RiskEngine"]
