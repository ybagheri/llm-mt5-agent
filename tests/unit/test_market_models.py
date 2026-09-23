"""Market model tests (pure domain, no MT5)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mt5_agent.domain.market import Candle, MarketSnapshot, SymbolInfo, Tick, Timeframe


def test_tick_validates_and_helpers() -> None:
    tick = Tick("EURUSD", datetime(2026, 1, 1, tzinfo=UTC), 1.1, 1.1002)
    assert tick.spread == pytest.approx(0.0002)
    assert tick.mid == pytest.approx(1.1001)


def test_tick_rejects_bad_quotes() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError):
        Tick("EURUSD", now, 0.0, 1.1)
    with pytest.raises(ValueError):
        Tick("EURUSD", now, 1.2, 1.1)
    with pytest.raises(ValueError):
        Tick("  ", now, 1.1, 1.2)


def test_candle_validates_ohlc() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    candle = Candle("EURUSD", Timeframe.M1, now, 1.0, 1.2, 0.9, 1.1)
    assert candle.is_bullish is True
    assert candle.range == pytest.approx(0.3)
    with pytest.raises(ValueError):
        Candle("EURUSD", Timeframe.M1, now, 1.0, 0.5, 0.9, 1.1)


def test_symbol_info_requires_symbol() -> None:
    with pytest.raises(ValueError):
        SymbolInfo("  ")


def test_snapshot_latest_helpers() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    candles = (
        Candle("EURUSD", Timeframe.M1, now, 1.0, 1.1, 0.9, 1.05),
        Candle("EURUSD", Timeframe.M1, now, 1.05, 1.15, 1.0, 1.12),
    )
    snap = MarketSnapshot("EURUSD", Timeframe.M1, now, candles=candles)
    assert snap.latest_close == pytest.approx(1.12)
    empty = MarketSnapshot("EURUSD", Timeframe.M1, now)
    assert empty.latest_candle is None
