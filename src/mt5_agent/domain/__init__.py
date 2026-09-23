"""Domain layer: pure models + ports (no MT5/HTTP/DB/LLM deps)."""

from __future__ import annotations

from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.errors import (
    MT5ConnectionError,
    MT5DataError,
    MT5Error,
    MT5LoginError,
    MT5NotAvailableError,
    MT5NotConnectedError,
)
from mt5_agent.domain.ports import MT5ConnectionPort
from mt5_agent.domain.terminal import (
    ConnectionConfig,
    ConnectionHealth,
    MT5Credentials,
    TerminalInfo,
)

__all__ = [
    "AccountInfo",
    "ConnectionConfig",
    "ConnectionHealth",
    "MT5ConnectionError",
    "MT5Credentials",
    "MT5DataError",
    "MT5Error",
    "MT5LoginError",
    "MT5NotAvailableError",
    "MT5NotConnectedError",
    "MT5ConnectionPort",
    "TerminalInfo",
]
