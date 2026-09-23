"""Application health: HEALTHY / DEGRADED / UNHEALTHY aggregation (Phase 12).

A healthy *process* is not a healthy *system*: this module composes per-component
probes (MT5 connectivity, market data, LLM provider, memory, executor) into one
`SystemHealth` verdict. Probes are injected callables so the domain stays free of
MT5/HTTP/DB dependencies and unit tests use fakes.

Severity order: HEALTHY < DEGRADED < UNHEALTHY (worst component wins).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class HealthStatus(StrEnum):
    """System/component health verdict."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    """One component's verdict (never raises; failures become UNHEALTHY)."""

    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "latency_ms": self.latency_ms,
        }


@dataclass(frozen=True, slots=True)
class SystemHealth:
    """Aggregated verdict across all probed components."""

    status: HealthStatus
    components: tuple[ComponentHealth, ...] = ()
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        object.__setattr__(self, "checked_at", _utc(self.checked_at))

    @property
    def healthy(self) -> bool:
        """True only when every component is HEALTHY (process-alive is not enough)."""
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "healthy": self.healthy,
            "checked_at": self.checked_at.isoformat(),
            "components": {c.name: c.to_dict() for c in self.components},
        }


def overall(components: tuple[ComponentHealth, ...]) -> HealthStatus:
    """Worst-component-wins aggregation (empty set is UNHEALTHY: nothing verified)."""
    if not components:
        return HealthStatus.UNHEALTHY
    if any(c.status == HealthStatus.UNHEALTHY for c in components):
        return HealthStatus.UNHEALTHY
    if any(c.status == HealthStatus.DEGRADED for c in components):
        return HealthStatus.DEGRADED
    return HealthStatus.HEALTHY


Probe = Callable[[], ComponentHealth]


class HealthService:
    """Runs injected probes and aggregates them (never raises)."""

    def __init__(self, probes: dict[str, Probe] | None = None) -> None:
        self._probes: dict[str, Probe] = dict(probes or {})

    @property
    def probe_names(self) -> tuple[str, ...]:
        return tuple(self._probes)

    def check(self) -> SystemHealth:
        """Run every probe; a raising probe becomes an UNHEALTHY component."""
        results: list[ComponentHealth] = []
        for name, probe in self._probes.items():
            try:
                reported = probe()
            except Exception as exc:  # probes must never break aggregation
                reported = ComponentHealth(name, HealthStatus.UNHEALTHY, str(exc))
            if reported.name != name:
                reported = ComponentHealth(
                    name, reported.status, reported.message, reported.latency_ms
                )
            results.append(reported)
        components = tuple(results)
        return SystemHealth(overall(components), components)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "ComponentHealth",
    "HealthService",
    "HealthStatus",
    "Probe",
    "SystemHealth",
    "overall",
]
