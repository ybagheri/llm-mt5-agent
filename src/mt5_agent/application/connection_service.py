"""Connection service: orchestrates the MT5 port with retry/reconnect policy.

Owns polling/synchronization policy (attempts, backoff) without touching the
MT5 API directly. All terminal access goes through :class:`MT5ConnectionPort`.
No trading functionality.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.errors import MT5Error
from mt5_agent.domain.ports import MT5ConnectionPort
from mt5_agent.domain.terminal import (
    ConnectionConfig,
    ConnectionHealth,
    MT5Credentials,
    TerminalInfo,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Deterministic reconnect policy."""

    max_attempts: int = 3
    delay_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.delay_seconds < 0:
            raise ValueError("delay_seconds must be >= 0")


class ConnectionService:
    """High-level, testable connection workflow."""

    def __init__(
        self,
        port: MT5ConnectionPort,
        retry: RetryPolicy | None = None,
    ) -> None:
        self._port = port
        self._retry = retry or RetryPolicy()

    @property
    def port(self) -> MT5ConnectionPort:
        return self._port

    def ensure_connected(
        self,
        config: ConnectionConfig,
        credentials: MT5Credentials | None = None,
    ) -> ConnectionHealth:
        """Connect with retries; returns the post-connect health record.

        Raises the last :class:`MT5Error` when all attempts fail (fail safely —
        callers must not trade without a healthy connection).
        """
        last_error: MT5Error | None = None
        for attempt in range(1, self._retry.max_attempts + 1):
            try:
                # Never log credentials (repr is masked, but avoid logging at all).
                logger.info(
                    "mt5 connect attempt",
                    extra={
                        "extra_fields": {
                            "attempt": attempt,
                            "max_attempts": self._retry.max_attempts,
                        }
                    },
                )
                self._port.connect(config, credentials)
                health = self._port.check_health()
                if health.connected:
                    return health
                last_error = MT5Error(f"health check failed: {health.error}")
            except MT5Error as exc:
                last_error = exc
                logger.warning(
                    "mt5 connect attempt failed",
                    extra={"extra_fields": {"attempt": attempt, "error": str(exc)}},
                )
            if attempt < self._retry.max_attempts and self._retry.delay_seconds > 0:
                time.sleep(self._retry.delay_seconds)
        assert last_error is not None
        raise last_error

    def disconnect(self) -> None:
        self._port.disconnect()

    def get_account(self) -> AccountInfo:
        return self._port.get_account_info()

    def get_terminal(self) -> TerminalInfo:
        return self._port.get_terminal_info()

    def health(self) -> ConnectionHealth:
        return self._port.check_health()

    def reconnect(
        self,
        config: ConnectionConfig,
        credentials: MT5Credentials | None = None,
    ) -> ConnectionHealth:
        """Disconnect (best effort) then :meth:`ensure_connected`."""
        try:
            self._port.disconnect()
        except Exception as exc:  # disconnection must not block reconnect
            logger.warning("mt5 disconnect during reconnect failed: %s", exc)
        return self.ensure_connected(config, credentials)


__all__ = ["ConnectionService", "RetryPolicy"]
