"""Connection service: orchestrates the MT5 port with retry/reconnect policy.

Owns polling/synchronization policy (attempts, backoff) without touching the
MT5 API directly. All terminal access goes through :class:`MT5ConnectionPort`.
No trading functionality.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
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
    """Deterministic reconnect policy with optional exponential backoff.

    `delay_for(attempt)` grows geometrically (`delay_seconds * backoff_factor **
    (attempt - 1)`, capped at `max_delay_seconds`) so repeated MT5 outages do
    not hammer the terminal. `backoff_factor=1.0` preserves the legacy fixed
    delay. No jitter: retries stay deterministic and test-friendly.
    """

    max_attempts: int = 3
    delay_seconds: float = 2.0
    backoff_factor: float = 1.0
    max_delay_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.delay_seconds < 0:
            raise ValueError("delay_seconds must be >= 0")
        if self.backoff_factor < 1.0:
            raise ValueError("backoff_factor must be >= 1.0")
        if self.max_delay_seconds is not None and self.max_delay_seconds < 0:
            raise ValueError("max_delay_seconds must be >= 0")

    def delay_for(self, attempt: int) -> float:
        """Delay before the next attempt after attempt `attempt` (1-indexed)."""
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        delay = self.delay_seconds * (self.backoff_factor ** (attempt - 1))
        if self.max_delay_seconds is not None:
            delay = min(delay, self.max_delay_seconds)
        return delay


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
            if attempt < self._retry.max_attempts:
                delay = self._retry.delay_for(attempt)
                if delay > 0:
                    time.sleep(delay)
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
        *,
        verify: Callable[[], None] | None = None,
    ) -> ConnectionHealth:
        """Disconnect (best effort), reconnect, then verify state before trading.

        `verify` re-reads account state, open positions, and pending orders and
        raises when the intended action is no longer valid. Pass it whenever a
        reconnect precedes execution: **never submit an order after reconnecting
        without re-verification** (prevents duplicates after ambiguous drops).
        """
        try:
            self._port.disconnect()
        except Exception as exc:  # disconnection must not block reconnect
            logger.warning("mt5 disconnect during reconnect failed: %s", exc)
        health = self.ensure_connected(config, credentials)
        logger.info(
            "mt5 reconnected",
            extra={
                "extra_fields": {
                    "account_login": health.account_login,
                    "trade_allowed": health.trade_allowed,
                }
            },
        )
        if verify is not None:
            verify()
            logger.info("mt5 post-reconnect verification passed")
        return health


__all__ = ["ConnectionService", "RetryPolicy"]
