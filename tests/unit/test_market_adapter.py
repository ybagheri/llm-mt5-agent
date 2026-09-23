"""Market adapter + service tests (FakeMT5 / FakePort, no terminal)."""

from __future__ import annotations

from collections import namedtuple
from datetime import UTC
from typing import Any

import pytest

from mt5_agent.application.market_service import MarketService
from mt5_agent.domain.errors import (
    MT5MarketDataError,
    MT5NotConnectedError,
    MT5SymbolNotFoundError,
)
from mt5_agent.domain.market import Candle, MarketSnapshot, SymbolInfo, Tick, Timeframe
from mt5_agent.domain.ports import MarketDataPort
from mt5_agent.infrastructure.mt5.market_adapter import MT5MarketDataAdapter

TickTuple = namedtuple("TickTuple", ["time", "bid", "ask", "last", "volume", "time_msc"])
RateTuple = namedtuple(
    "RateTuple",
    ["time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"],
)
SymbolTuple = namedtuple(
    "SymbolTuple",
    [
        "name",
        "description",
        "currency_base",
        "currency_profit",
        "digits",
        "point",
        "spread",
        "trade_mode",
        "volume_min",
        "volume_max",
        "volume_step",
        "trade_contract_size",
    ],
)


class FakeMT5:
    TIMEFRAME_M1 = 1
    TIMEFRAME_H1 = 16385

    def __init__(self) -> None:
        self.rates_calls: list[dict[str, Any]] = []
        self.fail_rates = False
        self.fail_tick = False
        self.unknown_symbol = False

    def copy_rates_from_pos(self, symbol: str, tf: Any, pos: int, count: int) -> Any:
        self.rates_calls.append({"symbol": symbol, "tf": tf, "pos": pos, "count": count})
        if self.fail_rates:
            return None
        base = 1_700_000_000
        return [
            RateTuple(base + i * 60, 1.0, 1.2, 0.9, 1.0 + i * 0.001, 10, 5, 0.0)
            for i in range(count)
        ]

    def symbol_info_tick(self, symbol: str) -> Any:
        if self.fail_tick:
            return None
        return TickTuple(1_700_000_000, 1.1000, 1.1002, 1.1001, 3.0, 1_700_000_000_000)

    def symbol_info(self, symbol: str) -> Any:
        if self.unknown_symbol:
            return None
        return SymbolTuple(
            symbol, "desc", "EUR", "USD", 5, 0.00001, 10, 4, 0.01, 50.0, 0.01, 100000.0
        )

    def last_error(self) -> Any:
        return (-1, "fake")


class FakeConnection:
    def __init__(self, connected: bool = True) -> None:
        self._connected = connected

    def is_connected(self) -> bool:
        return self._connected


def _adapter(**kwargs: Any) -> MT5MarketDataAdapter:
    return MT5MarketDataAdapter(mt5_module=FakeMT5(), **kwargs)


def test_get_candles_ok() -> None:
    adapter = _adapter()
    candles = adapter.get_candles("EURUSD", Timeframe.M1, count=5)
    assert len(candles) == 5
    assert candles[-1].close > candles[0].close


def test_get_tick_and_symbol_ok() -> None:
    adapter = _adapter()
    assert adapter.get_tick("EURUSD").bid > 0
    assert adapter.get_symbol_info("EURUSD").digits == 5


def test_unknown_symbol_raises() -> None:
    fake = FakeMT5()
    fake.unknown_symbol = True
    fake.fail_tick = True
    adapter = MT5MarketDataAdapter(mt5_module=fake)
    with pytest.raises(MT5SymbolNotFoundError):
        adapter.get_symbol_info("NOPE")
    with pytest.raises(MT5SymbolNotFoundError):
        adapter.get_tick("NOPE")


def test_rates_failure_raises() -> None:
    fake = FakeMT5()
    fake.fail_rates = True
    adapter = MT5MarketDataAdapter(mt5_module=fake)
    with pytest.raises(MT5MarketDataError):
        adapter.get_candles("EURUSD", Timeframe.M1, count=10)


def test_invalid_args_rejected() -> None:
    adapter = _adapter()
    with pytest.raises(MT5MarketDataError):
        adapter.get_candles("  ", Timeframe.M1)
    with pytest.raises(MT5MarketDataError):
        adapter.get_candles("EURUSD", Timeframe.M1, count=0)
    with pytest.raises(MT5MarketDataError):
        adapter.get_candles("EURUSD", Timeframe.M1, count=6000)
    with pytest.raises(MT5MarketDataError):
        adapter.get_candles("EURUSD", Timeframe.M1, start_pos=-1)


def test_not_connected_guard() -> None:
    adapter = _adapter(connection=FakeConnection(connected=False))
    with pytest.raises(MT5NotConnectedError):
        adapter.get_tick("EURUSD")


def test_snapshot_partial_on_tick_failure() -> None:
    fake = FakeMT5()
    fake.fail_tick = True
    adapter = MT5MarketDataAdapter(mt5_module=fake)
    snap = adapter.get_snapshot("EURUSD", Timeframe.M1, count=3)
    assert len(snap.candles) == 3
    assert snap.tick is None
    assert snap.symbol_info is not None


class FakePort(MarketDataPort):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_tick(self, symbol: str) -> Tick:
        self.calls.append(f"tick:{symbol}")
        from datetime import datetime

        return Tick(symbol, datetime(2026, 1, 1, tzinfo=UTC), 1.0, 1.1)

    def get_candles(
        self, symbol: str, timeframe: Timeframe, count: int = 100, start_pos: int = 0
    ) -> list[Candle]:
        self.calls.append(f"candles:{symbol}")
        from datetime import datetime

        now = datetime(2026, 1, 1, tzinfo=UTC)
        return [Candle(symbol, timeframe, now, 1.0, 1.1, 0.9, 1.05)]

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        self.calls.append(f"info:{symbol}")
        return SymbolInfo(symbol)

    def get_snapshot(self, symbol: str, timeframe: Timeframe, count: int = 100) -> MarketSnapshot:
        self.calls.append(f"snap:{symbol}")
        from datetime import datetime

        return MarketSnapshot(symbol, timeframe, datetime.now(UTC))


def test_market_service_validation_and_delegation() -> None:
    svc = MarketService(FakePort())
    tick = svc.get_tick("  EURUSD ")
    assert tick.symbol == "EURUSD"
    with pytest.raises(MT5MarketDataError):
        svc.get_tick("   ")
    with pytest.raises(MT5MarketDataError):
        svc.get_tick("X" * 33)
    snap = svc.get_snapshot("EURUSD", Timeframe.H1)
    assert snap.symbol == "EURUSD"
