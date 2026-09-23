"""Domain errors: pure, no external dependencies."""

from __future__ import annotations


class MT5Error(Exception):
    """Base class for all MT5-related domain errors."""


class MT5NotAvailableError(MT5Error):
    """Raised when the official MetaTrader5 package cannot be used.

    Reasons: non-Windows platform, package not installed, terminal missing.
    """


class MT5ConnectionError(MT5Error):
    """Raised when initialize()/connect fails."""

    def __init__(self, message: str, code: object = None) -> None:
        super().__init__(message)
        self.code = code


class MT5LoginError(MT5Error):
    """Raised when login() to a trading account fails."""

    def __init__(self, message: str, code: object = None) -> None:
        super().__init__(message)
        self.code = code


class MT5NotConnectedError(MT5Error):
    """Raised when an operation requires an active connection."""


class MT5DataError(MT5Error):
    """Raised when MT5 returns missing/invalid data (account/terminal info)."""


__all__ = [
    "MT5ConnectionError",
    "MT5DataError",
    "MT5Error",
    "MT5LoginError",
    "MT5NotAvailableError",
    "MT5NotConnectedError",
]
