"""MT5 trading-data adapter: open positions, pending + history orders, deals.

Read-only. The only MT5-touching module for trading state; strategies and
services use domain models via the ports.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from mt5_agent.domain.errors import MT5MarketDataError, MT5NotConnectedError
from mt5_agent.domain.ports import HistoryPort, MT5ConnectionPort, OrderPort, PositionPort
from mt5_agent.domain.trading import Deal, Order, Position
from mt5_agent.infrastructure.mt5.module import load_mt5
from mt5_agent.infrastructure.mt5.trading_mappers import map_deal, map_many, map_order, map_position


class MT5TradingDataAdapter(PositionPort, OrderPort, HistoryPort):
    """MT5-backed trading state. Inject `mt5_module` fakes in tests."""

    def __init__(
        self,
        mt5_module: Any | None = None,
        connection: MT5ConnectionPort | None = None,
    ) -> None:
        self._mt5 = mt5_module
        self._connection = connection

    # -- positions / orders --------------------------------------------
    def get_open_positions(self, symbol: str | None = None) -> list[Position]:
        mt5 = self._ensure_ready()
        name = self._clean_optional(symbol)
        raw = mt5.positions_get(symbol=name) if name else mt5.positions_get()
        return map_many(raw, map_position, what="positions")

    def get_pending_orders(self, symbol: str | None = None) -> list[Order]:
        mt5 = self._ensure_ready()
        name = self._clean_optional(symbol)
        raw = mt5.orders_get(symbol=name) if name else mt5.orders_get()
        return map_many(raw, map_order, what="orders")

    # -- history ---------------------------------------------------------
    def get_deals(
        self,
        date_from: datetime,
        date_to: datetime,
        symbol: str | None = None,
    ) -> list[Deal]:
        mt5 = self._ensure_ready()
        self._check_range(date_from, date_to)
        raw = mt5.history_deals_get(date_from, date_to)
        deals: list[Deal] = map_many(raw, map_deal, what="deals")
        name = self._clean_optional(symbol)
        if name:
            deals = [d for d in deals if d.symbol == name]
        return deals

    def get_history_orders(
        self,
        date_from: datetime,
        date_to: datetime,
        symbol: str | None = None,
    ) -> list[Order]:
        mt5 = self._ensure_ready()
        self._check_range(date_from, date_to)
        raw = mt5.history_orders_get(date_from, date_to)
        orders: list[Order] = map_many(
            raw, lambda row: map_order(row, what="history_order"), what="history_orders"
        )
        name = self._clean_optional(symbol)
        if name:
            orders = [o for o in orders if o.symbol == name]
        return orders

    # -- internals --------------------------------------------------------
    @staticmethod
    def _clean_optional(symbol: str | None) -> str | None:
        if symbol is None:
            return None
        name = symbol.strip()
        if not name:
            raise MT5MarketDataError("symbol filter must be non-empty")
        return name

    @staticmethod
    def _check_range(date_from: datetime, date_to: datetime) -> None:
        if date_to < date_from:
            raise MT5MarketDataError("date_to must be >= date_from")

    def _ensure_ready(self) -> Any:
        if self._connection is not None and not self._connection.is_connected():
            raise MT5NotConnectedError("Not connected. Call connect() first.")
        if self._mt5 is None:
            self._mt5 = load_mt5()
        return self._mt5


__all__ = ["MT5TradingDataAdapter"]
