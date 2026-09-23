"""Terminal / connection domain models (pure — no MT5 dependency)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TerminalInfo:
    """Snapshot of the connected MT5 terminal (read-only, Phase 01)."""

    company: str = ""
    name: str = ""
    path: str = ""
    trade_allowed: bool = False
    connected: bool = False
    build: int = 0
    max_bars: int = 0


@dataclass(frozen=True, slots=True)
class MT5Credentials:
    """Login credentials. Password is secret — never log it."""

    login: int
    password: str
    server: str

    def __repr__(self) -> str:  # never leak the password
        return f"MT5Credentials(login={self.login}, server={self.server!r}, password='***')"


@dataclass(frozen=True, slots=True)
class ConnectionConfig:
    """Non-secret connection options (safe to log)."""

    timeout_ms: int = 60_000
    portable: bool = False
    path: str | None = None
    login: int | None = None
    server: str | None = None


@dataclass(frozen=True, slots=True)
class ConnectionHealth:
    """Result of a connection health check."""

    connected: bool
    trade_allowed: bool = False
    account_login: int | None = None
    terminal_company: str = ""
    error: str = ""
    details: dict[str, object] = field(default_factory=dict)


__all__ = [
    "ConnectionConfig",
    "ConnectionHealth",
    "MT5Credentials",
    "TerminalInfo",
]
