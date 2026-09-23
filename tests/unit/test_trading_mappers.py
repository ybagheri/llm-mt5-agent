"""Trading mapper tests (namedtuple/dict rows, no MT5 import)."""

from __future__ import annotations

from collections import namedtuple

import pytest

from mt5_agent.domain.errors import MT5DataError
from mt5_agent.domain.trading import PositionSide
from mt5_agent.infrastructure.mt5.trading_mappers import (
    map_deal,
    map_many,
    map_order,
    map_position,
)

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


def test_map_position_buy() -> None:
    raw = PositionTuple(11, 1_700_000_000, 0, 0, 0.1, 1.1, 1.0, 1.3, 1.2, -0.5, 10.0, "EURUSD", "")
    pos = map_position(raw)
    assert pos.side == PositionSide.BUY
    assert pos.floating == pytest.approx(9.5)
    assert pos.signed_volume > 0


def test_map_position_bad_type() -> None:
    raw = PositionTuple(11, 1_700_000_000, 7, 0, 0.1, 1.1, 0, 0, 1.1, 0, 0, "EURUSD", "")
    with pytest.raises(MT5DataError):
        map_position(raw)


def test_map_position_none() -> None:
    with pytest.raises(MT5DataError):
        map_position(None)


def test_map_order_and_history() -> None:
    raw = OrderTuple(21, 1_700_000_000, 2, 7, 0.1, 0.1, 1.09, 0, 0, 1.1, "EURUSD", "", 1)
    order = map_order(raw)
    assert order.ticket == 21
    assert order.magic == 7
    hist = map_order(dict(raw._asdict()), what="history_order")
    assert hist.ticket == 21


def test_map_deal_net() -> None:
    raw = DealTuple(31, 30, 1_700_000_000, 0, 1, 0, 99, 0.1, 1.2, -0.2, 0, 5.0, 0, "EURUSD", "")
    deal = map_deal(raw)
    assert deal.position_id == 99
    assert deal.net == pytest.approx(4.8)


def test_map_many_none_is_empty() -> None:
    assert map_many(None, map_position, what="positions") == []
    with pytest.raises(MT5DataError):
        map_many(123, map_position, what="positions")
