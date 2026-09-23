"""MT5 package subpackage."""

from __future__ import annotations

from mt5_agent.infrastructure.mt5.connection_adapter import MT5ConnectionAdapter
from mt5_agent.infrastructure.mt5.mappers import map_account_info, map_terminal_info
from mt5_agent.infrastructure.mt5.market_adapter import MAX_CANDLES, MT5MarketDataAdapter
from mt5_agent.infrastructure.mt5.market_mappers import (
    map_candle,
    map_candles,
    map_symbol_info,
    map_tick,
)
from mt5_agent.infrastructure.mt5.module import load_mt5
from mt5_agent.infrastructure.mt5.timeframes import resolve_timeframe
from mt5_agent.infrastructure.mt5.trading_adapter import MT5TradingDataAdapter
from mt5_agent.infrastructure.mt5.trading_mappers import (
    map_deal,
    map_many,
    map_order,
    map_position,
)

__all__ = [
    "MAX_CANDLES",
    "MT5ConnectionAdapter",
    "MT5MarketDataAdapter",
    "MT5TradingDataAdapter",
    "load_mt5",
    "map_account_info",
    "map_candle",
    "map_candles",
    "map_deal",
    "map_many",
    "map_order",
    "map_position",
    "map_symbol_info",
    "map_terminal_info",
    "map_tick",
    "resolve_timeframe",
]
