"""MT5 market-data adapter (read-only; no order-sending code)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from mt5_agent.domain.errors import (
    MT5MarketDataError,
    MT5NotConnectedError,
    MT5SymbolNotFoundError,
)
from mt5_agent.domain.market import Candle, MarketSnapshot, SymbolInfo, Tick, Timeframe
from mt5_agent.domain.ports import MarketDataPort, MT5ConnectionPort
from mt5_agent.infrastructure.mt5.market_mappers import (
    map_candles,
    map_symbol_info,
    map_tick,
)
from mt5_agent.infrastructure.mt5.module import load_mt5
from mt5_agent.infrastructure.mt5.timeframes import resolve_timeframe

MAX_CANDLES = 5000


class MT5MarketDataAdapter(MarketDataPort):
    """MT5-backed market data. Inject `mt5_module` fakes in tests."""

    def __init__(
        self,
        mt5_module: Any | None = None,
        connection: MT5ConnectionPort | None = None,
    ) -> None:
        self._mt5 = mt5_module
        self._connection = connection

    # -- reads ---------------------------------------------------------
    def get_tick(self, symbol: str) -> Tick:
        name = self._clean_symbol(symbol)
        mt5 = self._ensure_ready()
        raw = mt5.symbol_info_tick(name)
        if raw is None:
            self._raise_unknown_or_data(mt5, name, what="tick")
        return map_tick(raw, name)

    def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        count: int = 100,
        start_pos: int = 0,
    ) -> list[Candle]:
        name = self._clean_symbol(symbol)
        self._check_count(count)
        self._check_start_pos(start_pos)
        mt5 = self._ensure_ready()
        tf_value = resolve_timeframe(mt5, timeframe)
        raw = mt5.copy_rates_from_pos(name, tf_value, start_pos, count)
        if raw is None:
            self._raise_unknown_or_data(mt5, name, what="candles")
        return map_candles(raw, name, timeframe)

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        name = self._clean_symbol(symbol)
        mt5 = self._ensure_ready()
        raw = mt5.symbol_info(name)
        if raw is None:
            raise MT5SymbolNotFoundError(name)
        return map_symbol_info(raw, name)

    def get_snapshot(
        self,
        symbol: str,
        timeframe: Timeframe,
        count: int = 100,
    ) -> MarketSnapshot:
        name = self._clean_symbol(symbol)
        candles = self.get_candles(name, timeframe, count=count)
        try:
            tick = self.get_tick(name)
        except MT5MarketDataError:
            tick = None
        try:
            info = self.get_symbol_info(name)
        except MT5MarketDataError:
            info = None
        return MarketSnapshot(
            symbol=name,
            timeframe=timeframe,
            fetched_at=datetime.now(UTC),
            candles=tuple(candles),
            tick=tick,
            symbol_info=info,
        )

    # -- internals ------------------------------------------------------
    @staticmethod
    def _clean_symbol(symbol: str) -> str:
        name = (symbol or "").strip()
        if not name:
            raise MT5MarketDataError("symbol must be non-empty")
        return name

    @staticmethod
    def _check_count(count: int) -> None:
        if not isinstance(count, int) or count < 1 or count > MAX_CANDLES:
            raise MT5MarketDataError(f"count must be 1..{MAX_CANDLES}, got {count!r}")

    @staticmethod
    def _check_start_pos(start_pos: int) -> None:
        if not isinstance(start_pos, int) or start_pos < 0:
            raise MT5MarketDataError(f"start_pos must be >= 0, got {start_pos!r}")

    def _ensure_ready(self) -> Any:
        if self._connection is not None and not self._connection.is_connected():
            raise MT5NotConnectedError("Not connected. Call connect() first.")
        if self._mt5 is None:
            self._mt5 = load_mt5()
        return self._mt5

    def _raise_unknown_or_data(self, mt5: Any, symbol: str, *, what: str) -> None:
        try:
            if mt5.symbol_info(symbol) is None:
                raise MT5SymbolNotFoundError(symbol)
        except MT5SymbolNotFoundError:
            raise
        except Exception:  # noqa: S110 — symbol probe is best-effort
            pass
        raise MT5MarketDataError(
            f"{what}({symbol}) unavailable: {self._last_error(mt5)}",
        )

    @staticmethod
    def _last_error(mt5: Any) -> Any:
        try:
            return mt5.last_error()
        except Exception:
            return "unknown error"


__all__ = ["MAX_CANDLES", "MT5MarketDataAdapter"]
