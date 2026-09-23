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
from mt5_agent.domain.execution import (
    ExecutionMode,
    ExecutionRecord,
    ExecutionStatus,
    OrderRequest,
)
from mt5_agent.domain.market import Candle, MarketSnapshot, SymbolInfo, Tick, Timeframe
from mt5_agent.domain.planning import (
    MemoryNote,
    PlannerInput,
    TradeAction,
    TradeProposal,
)
from mt5_agent.domain.ports import (
    HistoryPort,
    MarketDataPort,
    MT5ConnectionPort,
    OrderPort,
    PositionPort,
)
from mt5_agent.domain.strategy import (
    DecisionAction,
    Direction,
    MarketContext,
    Setup,
    StrategyContext,
    StrategyDecision,
    StrategySignal,
)
from mt5_agent.domain.terminal import (
    ConnectionConfig,
    ConnectionHealth,
    MT5Credentials,
    TerminalInfo,
)
from mt5_agent.domain.trading import (
    AccountState,
    Deal,
    Order,
    Position,
    PositionSide,
    TradeResult,
)

__all__ = [
    "AccountInfo",
    "AccountState",
    "Candle",
    "ConnectionConfig",
    "ConnectionHealth",
    "Deal",
    "DecisionAction",
    "Direction",
    "ExecutionMode",
    "ExecutionRecord",
    "ExecutionStatus",
    "HistoryPort",
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
    "MarketContext",
    "MarketDataPort",
    "MarketSnapshot",
    "MemoryNote",
    "Order",
    "OrderPort",
    "OrderRequest",
    "PlannerInput",
    "Position",
    "PositionPort",
    "PositionSide",
    "Setup",
    "StrategyContext",
    "StrategyDecision",
    "StrategySignal",
    "SymbolInfo",
    "TerminalInfo",
    "Tick",
    "Timeframe",
    "TradeAction",
    "TradeProposal",
    "TradeResult",
]
