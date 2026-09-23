"""Trading adapter + services tests (fakes only, no terminal)."""

from __future__ import annotations

from collections import namedtuple
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from mt5_agent.application.account_service import AccountService
from mt5_agent.application.history_service import HistoryService
from mt5_agent.application.order_service import OrderService
from mt5_agent.application.position_service import PositionService
from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.errors import MT5MarketDataError, MT5NotConnectedError
from mt5_agent.domain.trading import Deal
from mt5_agent.infrastructure.mt5.trading_adapter import MT5TradingDataAdapter

PositionTuple = namedtuple(
    "PositionTuple",
    [
        "ticket",
        "time",
        "type",
        "magic",
        "volume",
        "price_open",
        "sl",
        "tp",
        "price_current",
        "swap",
        "profit",
        "symbol",
        "comment",
    ],
)
OrderTuple = namedtuple(
    "OrderTuple",
    [
        "ticket",
        "time_setup",
        "type",
        "magic",
        "volume_current",
        "volume_initial",
        "price_open",
        "sl",
        "tp",
        "price_current",
        "symbol",
        "comment",
        "state",
    ],
)
DealTuple = namedtuple(
    "DealTuple",
    [
        "ticket",
        "order_ticket",
        "time",
        "type",
        "entry",
        "magic",
        "position_id",
        "volume",
        "price",
        "commission",
        "swap",
        "profit",
        "fee",
        "symbol",
        "comment",
    ],
)


class FakeMT5:
    def __init__(self) -> None:
        self.positions_payload: Any = [
            PositionTuple(1, 1_700_000_000, 0, 0, 0.1, 1.1, 0, 0, 1.2, 0.0, 5.0, "EURUSD", ""),
            PositionTuple(2, 1_700_000_000, 1, 0, 0.2, 1.3, 0, 0, 1.2, -1.0, 4.0, "EURUSD", ""),
        ]
        self.orders_payload: Any = [
            OrderTuple(11, 1_700_000_000, 2, 0, 0.1, 0.1, 1.09, 0, 0, 1.1, "EURUSD", "", 1),
        ]
        self.deals_payload: Any = [
            DealTuple(21, 20, 1_700_000_000, 0, 1, 0, 99, 0.1, 1.2, -0.2, 0, 5.0, 0, "EURUSD", ""),
            DealTuple(22, 20, 1_700_000_060, 1, 1, 0, 99, 0.1, 1.21, 0, 0, -1.0, 0, "EURUSD", ""),
        ]
        self.history_orders_payload: Any = []

    def positions_get(self, *args: Any, **kwargs: Any) -> Any:
        symbol = kwargs.get("symbol")
        if symbol:
            return [p for p in self.positions_payload if p.symbol == symbol]
        return self.positions_payload

    def orders_get(self, *args: Any, **kwargs: Any) -> Any:
        return self.orders_payload

    def history_deals_get(self, *args: Any, **kwargs: Any) -> Any:
        return self.deals_payload

    def history_orders_get(self, *args: Any, **kwargs: Any) -> Any:
        return self.history_orders_payload

    def last_error(self) -> Any:
        return (0, "ok")


class FakeConnection:
    def __init__(self, account: AccountInfo) -> None:
        self._account = account

    def get_account_info(self) -> AccountInfo:
        return self._account

    def is_connected(self) -> bool:
        return True


class OfflineConnection(FakeConnection):
    def is_connected(self) -> bool:
        return False


def _account() -> AccountInfo:
    return AccountInfo(1, "S", "USD", 1000.0, 1010.0, 50.0, 960.0, 10.0)


def test_adapter_positions_orders_deals() -> None:
    adapter = MT5TradingDataAdapter(mt5_module=FakeMT5())
    positions = adapter.get_open_positions()
    assert len(positions) == 2
    assert adapter.get_open_positions("EURUSD")[0].ticket == 1
    assert adapter.get_open_positions("XAUUSD") == []
    assert len(adapter.get_pending_orders()) == 1
    now = datetime.now(UTC)
    deals = adapter.get_deals(now - timedelta(days=1), now)
    assert len(deals) == 2
    assert adapter.get_deals(now - timedelta(days=1), now, symbol="XAUUSD") == []
    with pytest.raises(MT5MarketDataError):
        adapter.get_deals(now, now - timedelta(days=1))


def test_adapter_offline_guard() -> None:
    adapter = MT5TradingDataAdapter(mt5_module=FakeMT5(), connection=OfflineConnection(_account()))
    with pytest.raises(MT5NotConnectedError):
        adapter.get_open_positions()


def test_services_aggregate() -> None:
    adapter = MT5TradingDataAdapter(mt5_module=FakeMT5())
    positions = PositionService(adapter)
    assert positions.exposure_volume() == pytest.approx(0.3)
    assert positions.net_volume() == pytest.approx(-0.1)
    assert positions.floating_profit() == pytest.approx(8.0)
    assert OrderService(adapter).count() == 1

    history = HistoryService(adapter)
    deals = history.recent_deals(days=7)
    assert len(deals) == 2
    assert history.realized_profit(deals) == pytest.approx(3.8)
    results = history.closed_results(deals)
    assert len(results) == 1
    assert results[0].position_id == 99
    assert results[0].net == pytest.approx(3.8)
    with pytest.raises(MT5MarketDataError):
        history.recent_deals(days=0)

    account = AccountService(FakeConnection(_account()), adapter, adapter)
    state = account.get_state()
    assert state.open_positions == 2
    assert state.pending_orders == 1
    assert state.exposure_volume == pytest.approx(0.3)
    assert state.margin_level == pytest.approx(2020.0)


def test_closed_results_skips_zero_position() -> None:
    history = HistoryService(MT5TradingDataAdapter(mt5_module=FakeMT5()))
    now = datetime.now(UTC)
    balance_deal = Deal(99, 0, 0, "USD", 2, 0, 0.0, 1.0, profit=10.0, time=now)
    assert history.closed_results([balance_deal]) == []
