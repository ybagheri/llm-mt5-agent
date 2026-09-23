"""Market mapper tests (dict/namedtuple/sequence rows, no MT5 import)."""

from __future__ import annotations

from collections import namedtuple

import pytest

from mt5_agent.domain.errors import MT5DataError
from mt5_agent.domain.market import Timeframe
from mt5_agent.infrastructure.mt5.market_mappers import (
    map_candle,
    map_candles,
    map_symbol_info,
    map_tick,
)

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


def test_map_tick_from_namedtuple() -> None:
    raw = TickTuple(1_700_000_000, 1.1000, 1.1002, 1.1001, 5.0, 1_700_000_000_500)
    tick = map_tick(raw, "EURUSD")
    assert tick.bid == pytest.approx(1.1)
    assert tick.time.microsecond == 500_000


def test_map_tick_from_dict() -> None:
    tick = map_tick({"time": 1_700_000_000, "bid": 1.0, "ask": 1.1}, "XAUUSD")
    assert tick.symbol == "XAUUSD"
    assert tick.spread == pytest.approx(0.1)


def test_map_tick_none_raises() -> None:
    with pytest.raises(MT5DataError):
        map_tick(None, "EURUSD")


def test_map_candles_from_mixed_rows() -> None:
    rows = [
        RateTuple(1_700_000_000, 1.0, 1.2, 0.9, 1.1, 10, 5, 0.0),
        {
            "time": 1_700_000_060,
            "open": 1.1,
            "high": 1.3,
            "low": 1.0,
            "close": 1.2,
            "tick_volume": 7,
            "spread": 3,
            "real_volume": 0.0,
        },
    ]
    candles = map_candles(rows, "EURUSD", Timeframe.M1)
    assert len(candles) == 2
    assert candles[1].close == pytest.approx(1.2)


def test_map_candles_empty_and_none_raise() -> None:
    with pytest.raises(MT5DataError):
        map_candles([], "EURUSD", Timeframe.M1)
    with pytest.raises(MT5DataError):
        map_candles(None, "EURUSD", Timeframe.M1)


def test_map_candle_validates() -> None:
    with pytest.raises(MT5DataError):
        map_candle(
            {"time": 1, "open": 1.0, "high": 0.5, "low": 0.4, "close": 0.9}, "EURUSD", Timeframe.M1
        )


def test_map_symbol_info() -> None:
    raw = SymbolTuple(
        "EURUSD", "Euro vs US Dollar", "EUR", "USD", 5, 0.00001, 12, 4, 0.01, 100.0, 0.01, 100000.0
    )
    info = map_symbol_info(raw, "EURUSD")
    assert info.digits == 5
    assert info.spread == 12
    assert info.min_volume == pytest.approx(0.01)
