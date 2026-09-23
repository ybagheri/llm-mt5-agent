"""Mapper tests: raw MT5 payloads -> domain models (no MT5 import)."""

from __future__ import annotations

from collections import namedtuple
from types import SimpleNamespace

import pytest

from mt5_agent.domain.errors import MT5DataError
from mt5_agent.infrastructure.mt5.mappers import map_account_info, map_terminal_info

AccountTuple = namedtuple(
    "AccountTuple",
    [
        "login",
        "server",
        "currency",
        "balance",
        "equity",
        "margin",
        "margin_free",
        "profit",
        "leverage",
        "trade_allowed",
        "name",
    ],
)
TerminalTuple = namedtuple(
    "TerminalTuple",
    ["company", "name", "path", "trade_allowed", "connected", "build", "maxbars"],
)


def _account_raw() -> AccountTuple:
    return AccountTuple(
        123, "Demo-Server", "USD", 10000.0, 10100.0, 100.0, 9900.0, 100.0, 100, True, "Trader"
    )


def _terminal_raw() -> TerminalTuple:
    return TerminalTuple("MetaQuotes", "MT5", "C:/mt5/terminal64.exe", True, True, 5000, 100000)


def test_map_account_from_namedtuple() -> None:
    acc = map_account_info(_account_raw())
    assert acc.login == 123
    assert acc.server == "Demo-Server"
    assert acc.free_margin == 9900.0
    assert acc.trade_allowed is True


def test_map_account_from_dict_and_namespaces() -> None:
    raw = {
        "login": 7,
        "server": "S",
        "currency": "EUR",
        "balance": 1.0,
        "equity": 2.0,
        "margin": 0.0,
        "free_margin": 2.0,
        "profit": 1.0,
    }
    acc = map_account_info(raw)
    assert acc.login == 7
    ns = SimpleNamespace(
        login=9,
        server="X",
        currency="USD",
        balance=5.0,
        equity=5.0,
        margin=0.0,
        margin_free=5.0,
        profit=0.0,
    )
    assert map_account_info(ns).login == 9


def test_map_account_none_raises() -> None:
    with pytest.raises(MT5DataError, match="account_info"):
        map_account_info(None)


def test_map_account_bad_type_raises() -> None:
    with pytest.raises(MT5DataError):
        map_account_info(12345)


def test_map_terminal_from_namedtuple() -> None:
    term = map_terminal_info(_terminal_raw())
    assert term.connected is True
    assert term.company == "MetaQuotes"
    assert term.max_bars == 100000


def test_map_terminal_none_raises() -> None:
    with pytest.raises(MT5DataError, match="terminal_info"):
        map_terminal_info(None)
