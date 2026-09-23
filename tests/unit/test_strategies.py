"""NullStrategy + MeasureMove/Donchian tests (synthetic candles, deterministic)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mt5_agent.domain.market import Candle, MarketSnapshot, Timeframe
from mt5_agent.domain.strategy import Direction, MarketContext
from mt5_agent.strategies.measure_move import (
    DonchianBreakoutStrategy,
    MeasureMoveParams,
)
from mt5_agent.strategies.null_strategy import NullStrategy


def _candles(closes: list[float], symbol: str = "EURUSD") -> tuple[Candle, ...]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    out: list[Candle] = []
    for i, close in enumerate(closes):
        # Build consistent OHLC around close so validation passes.
        open_ = closes[i - 1] if i else close
        high = max(open_, close) + 0.0005
        low = min(open_, close) - 0.0005
        out.append(Candle(symbol, Timeframe.M1, base, open_, high, low, close))
        base = base.replace(minute=(base.minute + 1) % 60)
    return tuple(out)


def _context(closes: list[float]) -> MarketContext:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    snap = MarketSnapshot("EURUSD", Timeframe.M1, now, candles=_candles(closes))
    return MarketContext("EURUSD", Timeframe.M1, snap)


def test_null_always_flat() -> None:
    signal = NullStrategy().analyze(_context([1.1, 1.2, 1.3]))
    assert signal.direction == Direction.FLAT
    assert signal.confidence == 0.0
    assert signal.setups == ()


def test_donchian_long_breakout() -> None:
    closes = [1.1000, 1.1010, 1.1020, 1.1015, 1.1050]
    signal = DonchianBreakoutStrategy(MeasureMoveParams(lookback=4)).analyze(_context(closes))
    assert signal.direction == Direction.LONG
    assert len(signal.setups) == 1
    assert signal.setups[0].direction == Direction.LONG
    assert signal.facts["prior_high"] == pytest.approx(1.1025)


def test_donchian_short_breakout() -> None:
    closes = [1.1050, 1.1040, 1.1030, 1.1035, 1.1000]
    signal = DonchianBreakoutStrategy(MeasureMoveParams(lookback=4)).analyze(_context(closes))
    assert signal.direction == Direction.SHORT


def test_donchian_range_is_flat() -> None:
    closes = [1.1000, 1.1010, 1.1005, 1.1008, 1.1002]
    signal = DonchianBreakoutStrategy(MeasureMoveParams(lookback=4)).analyze(_context(closes))
    assert signal.direction == Direction.FLAT
    assert signal.confidence == 0.0


def test_insufficient_data_is_flat() -> None:
    signal = DonchianBreakoutStrategy().analyze(_context([1.1]))
    assert signal.direction == Direction.FLAT
    assert "need >=" in str(signal.facts.get("skip", ""))


def test_confirm_hook_veto() -> None:
    class Veto(DonchianBreakoutStrategy):
        name = "veto"

        def confirm(self, latest: Candle, window: list[Candle], direction: Direction) -> bool:
            return False

    closes = [1.1000, 1.1010, 1.1020, 1.1015, 1.1050]
    signal = Veto(MeasureMoveParams(lookback=4)).analyze(_context(closes))
    assert signal.direction == Direction.FLAT


def test_params_validation() -> None:
    with pytest.raises(ValueError):
        MeasureMoveParams(lookback=1)
    with pytest.raises(ValueError):
        MeasureMoveParams(breakout_confidence=2.0)


def test_base_is_abstract() -> None:
    from mt5_agent.strategies.base import Strategy

    with pytest.raises(TypeError):
        Strategy()  # type: ignore[abstract]
