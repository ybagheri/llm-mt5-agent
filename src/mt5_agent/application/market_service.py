"""Market service: validated orchestration over a MarketDataPort."""

from __future__ import annotations

from mt5_agent.domain.errors import MT5MarketDataError
from mt5_agent.domain.market import Candle, MarketSnapshot, SymbolInfo, Tick, Timeframe
from mt5_agent.domain.ports import MarketDataPort
from mt5_agent.infrastructure.mt5.market_adapter import MAX_CANDLES


class MarketService:
    """Application-level market reads with deterministic validation."""

    def __init__(self, port: MarketDataPort) -> None:
        self._port = port

    @property
    def port(self) -> MarketDataPort:
        return self._port

    def get_tick(self, symbol: str) -> Tick:
        return self._port.get_tick(self._clean(symbol))

    def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        count: int = 100,
        start_pos: int = 0,
    ) -> list[Candle]:
        return self._port.get_candles(self._clean(symbol), timeframe, count, start_pos)

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        return self._port.get_symbol_info(self._clean(symbol))

    def get_snapshot(
        self,
        symbol: str,
        timeframe: Timeframe,
        count: int = 100,
    ) -> MarketSnapshot:
        return self._port.get_snapshot(self._clean(symbol), timeframe, count)

    @staticmethod
    def _clean(symbol: str) -> str:
        name = (symbol or "").strip()
        if not name:
            raise MT5MarketDataError("symbol must be non-empty")
        if len(name) > 32:
            raise MT5MarketDataError(f"symbol too long: {name!r}")
        return name


__all__ = ["MAX_CANDLES", "MarketService"]
