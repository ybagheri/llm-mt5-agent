"""Risk domain: codes, context, results (pure, deterministic)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class ViolationCode(StrEnum):
    """Explicit rejection reasons (stable strings for audit/logs)."""

    MAX_RISK_EXCEEDED = "MAX_RISK_EXCEEDED"
    MAX_DAILY_LOSS_EXCEEDED = "MAX_DAILY_LOSS_EXCEEDED"
    MAX_POSITIONS_EXCEEDED = "MAX_POSITIONS_EXCEEDED"
    MAX_EXPOSURE_EXCEEDED = "MAX_EXPOSURE_EXCEEDED"
    SYMBOL_NOT_ALLOWED = "SYMBOL_NOT_ALLOWED"
    SESSION_CLOSED = "SESSION_CLOSED"
    SPREAD_TOO_HIGH = "SPREAD_TOO_HIGH"
    STOP_LOSS_REQUIRED = "STOP_LOSS_REQUIRED"
    TAKE_PROFIT_REQUIRED = "TAKE_PROFIT_REQUIRED"
    STOP_TOO_CLOSE = "STOP_TOO_CLOSE"
    DUPLICATE_TRADE = "DUPLICATE_TRADE"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    ACCOUNT_UNSAFE = "ACCOUNT_UNSAFE"


@dataclass(frozen=True, slots=True)
class Violation:
    """Single rule breach."""

    code: ViolationCode
    message: str
    rule: str = ""

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("message must be non-empty")


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Engine verdict: approved iff no violations. Never modified silently."""

    approved: bool
    violations: tuple[Violation, ...] = ()
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.approved and self.violations:
            raise ValueError("approved results carry no violations")
        if not self.approved and not self.violations:
            raise ValueError("rejections require at least one violation")
        object.__setattr__(self, "checked_at", _utc(self.checked_at))

    @property
    def codes(self) -> tuple[ViolationCode, ...]:
        return tuple(v.code for v in self.violations)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = ["ValidationResult", "Violation", "ViolationCode"]
