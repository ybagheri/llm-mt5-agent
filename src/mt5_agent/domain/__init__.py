"""Domain layer: pure models + ports (no MT5/HTTP/DB/LLM deps)."""

from __future__ import annotations

from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.errors import (
    MT5ConnectionError,
    MT5DataError,
    MT5Error,
    MT5LoginError,
    MT5MarketDataError,
    MT5NotAvailableError,
    MT5NotConnectedError,
    MT5SymbolNotFoundError,
)
from mt5_agent.domain.market import Candle, MarketSnapshot, SymbolInfo, Tick, Timeframe
from mt5_agent.domain.ports import MarketDataPort, MT5ConnectionPort
from mt5_agent.domain.terminal import (
    ConnectionConfig,
    ConnectionHealth,
    MT5Credentials,
    TerminalInfo,
)

__all__ = [
    "AccountInfo",
    "Candle",
    "ConnectionConfig",
    "ConnectionHealth",
    "MT5ConnectionError",
    "MT5ConnectionPort",
    "MT5Credentials",
    "MT5DataError",
    "MT5Error",
    "MT5LoginError",
    "MT5MarketDataError",
    "MT5NotAvailableError",
    "MT5NotConnectedError",
    "MT5SymbolNotFoundError",
    "MarketDataPort",
    "MarketSnapshot",
    "SymbolInfo",
    "TerminalInfo",
    "Tick",
    "Timeframe",
]
