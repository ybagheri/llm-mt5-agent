"""Fail-safe watchdog (Phase 12): detect degradation, halt trading activity.

The watchdog observes agent cycles, MT5/LLM/execution failures, and market-data
freshness. When tripped it reports UNHEALTHY and `should_halt()` becomes True,
telling the orchestrator to stop starting new cycles and new trade submissions.

It must fail safely: it can only *reduce* activity (halt), never increase it —
no retries, no order submission, no parameter loosening. In-flight DRY_RUN/DEMO
cycles finish; open positions are never touched (shutdown never closes them).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from mt5_agent.application.health import HealthStatus


@dataclass(frozen=True, slots=True)
class WatchdogConfig:
    """Trip thresholds (conservative defaults; tighten via settings)."""

    max_consecutive_failures: int = 5
    stale_after_s: float = 300.0

    def __post_init__(self) -> None:
        if self.max_consecutive_failures < 1:
            raise ValueError("max_consecutive_failures must be >= 1")
        if self.stale_after_s < 0:
            raise ValueError("stale_after_s must be >= 0")


class Watchdog:
    """In-memory failure/staleness tracker (thread-hostile free: single loop use)."""

    def __init__(self, config: WatchdogConfig | None = None) -> None:
        self._config = config or WatchdogConfig()
        self._consecutive: dict[str, int] = {}
        self._totals: dict[str, int] = {"success": 0, "failure": 0}
        self._last_error: str = ""
        self._last_observation_at: datetime | None = None
        self._tripped_at: datetime | None = None

    @property
    def config(self) -> WatchdogConfig:
        return self._config

    def note_success(self, kind: str = "cycle") -> None:
        """Record a healthy outcome; resets the consecutive-failure counter."""
        self._consecutive[kind] = 0
        self._totals["success"] += 1

    def note_failure(self, kind: str = "cycle", error: str = "") -> None:
        """Record a failure; trips the watchdog at the configured threshold."""
        self._consecutive[kind] = self._consecutive.get(kind, 0) + 1
        self._totals["failure"] += 1
        if error:
            self._last_error = error[-500:]
        if (
            self._consecutive[kind] >= self._config.max_consecutive_failures
            and self._tripped_at is None
        ):
            self._tripped_at = datetime.now(UTC)

    def note_observation(self, at: datetime | None = None) -> None:
        """Record fresh market data (call after every successful OBSERVE stage)."""
        observed = at or datetime.now(UTC)
        self._last_observation_at = observed if observed.tzinfo else observed.replace(tzinfo=UTC)

    def reset(self) -> None:
        """Manual recovery after an operator reviewed the cause (auditable)."""
        self._consecutive.clear()
        self._tripped_at = None
        self._last_error = ""

    def status(self) -> HealthStatus:
        """Current verdict: UNHEALTHY when tripped, DEGRADED on stale data."""
        if self._tripped_at is not None:
            return HealthStatus.UNHEALTHY
        if any(
            count >= self._config.max_consecutive_failures for count in self._consecutive.values()
        ):
            return HealthStatus.UNHEALTHY
        if self._last_observation_at is not None and self._config.stale_after_s > 0:
            age = (datetime.now(UTC) - self._last_observation_at).total_seconds()
            if age > self._config.stale_after_s:
                return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def should_halt(self) -> bool:
        """True when the orchestrator must stop starting new cycles/trades."""
        return self.status() == HealthStatus.UNHEALTHY

    def snapshot(self) -> dict[str, Any]:
        """Operator-readable state (safe to log: no secrets, no positions)."""
        return {
            "status": self.status().value,
            "halt": self.should_halt(),
            "consecutive_failures": dict(self._consecutive),
            "totals": dict(self._totals),
            "last_error": self._last_error,
            "last_observation_at": (
                self._last_observation_at.isoformat() if self._last_observation_at else None
            ),
            "tripped_at": self._tripped_at.isoformat() if self._tripped_at else None,
        }


__all__ = ["Watchdog", "WatchdogConfig"]
