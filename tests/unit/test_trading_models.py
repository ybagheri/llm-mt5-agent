"""Trading model tests (pure domain)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.trading import (
    AccountState,
    Deal,
    Order,
    Position,
    PositionSide,
    TradeResult,
)


def _pos(**kwargs: object) -> Position:
    base: dict[str, object] = {
        "ticket": 1,
        "symbol": "EURUSD",
        "side": PositionSide.BUY,
        "volume": 0.1,
        "price_open": 1.1,
        "price_current": 1.2,
    }
    base.update(kwargs)
    return Position(**base)  # type: ignore[arg-type]


def test_position_helpers() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    buy = _pos(time=now, profit=10.0, swap=-1.0)
    assert buy.floating == pytest.approx(9.0)
    assert buy.signed_volume == pytest.approx(0.1)
    sell = _pos(side=PositionSide.SELL, volume=0.2)
    assert sell.signed_volume == pytest.approx(-0.2)


def test_position_validation() -> None:
    with pytest.raises(ValueError):
        _pos(ticket=0)
    with pytest.raises(ValueError):
        _pos(symbol="  ")
    with pytest.raises(ValueError):
        _pos(volume=0.0)


def test_deal_net_and_result_net() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    deal = Deal(
        1,
        2,
        99,
        "EURUSD",
        0,
        1,
        0.1,
        1.2,
        profit=5.0,
        commission=-0.5,
        swap=-0.1,
        fee=-0.2,
        time=now,
    )
    assert deal.net == pytest.approx(4.2)
    result = TradeResult(99, "EURUSD", 0.1, 5.0, commission=-0.5, swap=-0.1, fee=-0.2)
    assert result.net == pytest.approx(4.2)


def test_account_state_helpers() -> None:
    acc = AccountInfo(1, "S", "USD", 1000.0, 1100.0, 100.0, 1000.0, 100.0)
    state = AccountState(acc, open_positions=2, exposure_volume=0.3, floating_profit=9.0)
    assert state.balance == pytest.approx(1000.0)
    assert state.margin_level == pytest.approx(1100.0)
    assert Order(5, "EURUSD", 2, 0.1, 0.1, 1.09).ticket == 5
