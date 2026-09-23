"""Agent cycle models: observable per-stage outcomes (no I/O)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class StageStatus(StrEnum):
    """Per-stage outcome."""

    OK = "OK"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class Stage(StrEnum):
    """Lifecycle stages in execution order."""

    OBSERVE = "OBSERVE"
    CONTEXT = "CONTEXT"
    STRATEGY = "STRATEGY"
    MEMORY = "MEMORY"
    PLAN = "PLAN"
    SUPERVISE = "SUPERVISE"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    MEMORY_UPDATE = "MEMORY_UPDATE"


@dataclass(frozen=True, slots=True)
class StageOutcome:
    """One stage's result (testable, loggable)."""

    stage: Stage
    status: StageStatus
    summary: str
    at: datetime = field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("summary must be non-empty")
        object.__setattr__(self, "at", _utc(self.at))


@dataclass(frozen=True, slots=True)
class AgentCycle:
    """Full lifecycle result: every stage recorded in order."""

    cycle_id: str
    symbol: str
    timeframe: str
    stages: tuple[StageOutcome, ...]
    started_at: datetime
    finished_at: datetime
    error: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "started_at", _utc(self.started_at))
        object.__setattr__(self, "finished_at", _utc(self.finished_at))

    @property
    def ok(self) -> bool:
        return not self.error and all(s.status != StageStatus.FAILED for s in self.stages)

    def stage(self, stage: Stage) -> StageOutcome | None:
        for outcome in self.stages:
            if outcome.stage == stage:
                return outcome
        return None


def new_cycle_id() -> str:
    return uuid.uuid4().hex[:12]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = ["AgentCycle", "Stage", "StageOutcome", "StageStatus", "new_cycle_id"]
