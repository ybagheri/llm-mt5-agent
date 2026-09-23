"""Dashboard tests: provider sections, costs, HTTP read-only contract."""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from typing import Any

from mt5_agent.application.account_service import AccountService
from mt5_agent.application.market_service import MarketService
from mt5_agent.application.order_service import OrderService
from mt5_agent.application.position_service import PositionService
from mt5_agent.application.strategy_service import StrategyService
from mt5_agent.dashboard.app import DashboardApp
from mt5_agent.dashboard.costs import estimate_cost_usd
from mt5_agent.dashboard.provider import DashboardStateProvider
from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.market import Candle, MarketSnapshot, SymbolInfo, Tick, Timeframe
from mt5_agent.memory.memories import StrategyMemory, TradeMemory, WorldMemory
from mt5_agent.memory.sqlite_store import SQLiteMemoryStore
from mt5_agent.risk.config import RiskConfig
from mt5_agent.strategies.null_strategy import NullStrategy


def _snapshot() -> MarketSnapshot:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    candle = Candle("EURUSD", Timeframe.M1, now, 1.0, 1.1, 0.9, 1.05)
    tick = Tick("EURUSD", now, 1.04, 1.06)
    return MarketSnapshot("EURUSD", Timeframe.M1, now, candles=(candle,), tick=tick)


class FakeMarketPort:
    def get_tick(self, symbol: str) -> Any:
        return _snapshot().tick

    def get_candles(
        self, symbol: str, timeframe: Timeframe, count: int = 100, start_pos: int = 0
    ) -> Any:
        return list(_snapshot().candles)

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        return SymbolInfo(symbol, point=0.00001, digits=5)

    def get_snapshot(self, symbol: str, timeframe: Timeframe, count: int = 100) -> MarketSnapshot:
        return _snapshot()


class FakeConnection:
    def get_account_info(self) -> AccountInfo:
        return AccountInfo(1, "S", "USD", 1000.0, 1010.0, 50.0, 960.0, 10.0, trade_allowed=True)

    def is_connected(self) -> bool:
        return True


class FakePositions:
    def get_open_positions(self, symbol: str | None = None) -> list[Any]:
        return []


class FakeOrders:
    def get_pending_orders(self, symbol: str | None = None) -> list[Any]:
        return []


class FakeHistory:
    def deals(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []

    def realized_profit(self, deals: list[Any]) -> float:
        return 0.0


def _provider(**overrides: Any) -> tuple[DashboardStateProvider, SQLiteMemoryStore]:
    store = SQLiteMemoryStore(":memory:")
    market = MarketService(FakeMarketPort())
    conn = FakeConnection()
    account = AccountService(conn, FakePositions(), FakeOrders())
    params = {
        "market": market,
        "account": account,
        "positions": PositionService(FakePositions()),
        "orders": OrderService(FakeOrders()),
        "strategies": StrategyService([NullStrategy()]),
        "risk_config": RiskConfig(),
        "history": FakeHistory(),
        "trade_memory": TradeMemory(store),
        "strategy_memory": StrategyMemory(store),
        "world_memory": WorldMemory(store),
        "version": "0.0",
        "trading_mode": "dry_run",
    }
    params.update(overrides)
    return DashboardStateProvider(**params), store  # type: ignore[arg-type]


def test_state_sections() -> None:
    provider, store = _provider()
    try:
        state = provider.build("EURUSD", Timeframe.M1)
        assert state.error == ""
        assert state.account.balance == 1000.0
        assert state.market.bid == 1.04
        assert state.market.spread_points == 2000.0
        assert state.market.session_open is True
        assert state.agent.strategy == "null"
        assert state.risk.max_open_positions == 3
        assert state.llm.provider == "none"
        assert state.memory.recent_decisions == ()
    finally:
        store.close()


def test_state_core_failure_reports_error() -> None:
    class BoomMarket(FakeMarketPort):
        def get_snapshot(
            self, symbol: str, timeframe: Timeframe, count: int = 100
        ) -> MarketSnapshot:
            raise RuntimeError("down")

    provider, store = _provider(market=MarketService(BoomMarket()))
    try:
        assert provider.build("EURUSD", Timeframe.M1).error == "down"
    finally:
        store.close()


def test_memory_sections_listed() -> None:
    provider, store = _provider()
    try:
        TradeMemory(store).record_outcome("EURUSD", "closed +1", net=1.0)
        WorldMemory(store).note("", "regime note")
        state = provider.build("EURUSD", Timeframe.M1)
        assert len(state.memory.recent_trades) == 1
        assert len(state.memory.recent_events) == 1
    finally:
        store.close()


def test_llm_usage_and_cost() -> None:
    from mt5_agent.ai.models import LLMResponse, LLMUsage

    provider, store = _provider()
    try:
        assert provider.build("EURUSD", Timeframe.M1).llm.estimated_cost_usd is None
        provider.record_llm(
            LLMResponse(
                "hi", "openai", "gpt-4o-mini", 12.0, LLMUsage(1_000_000, 1_000_000, 2_000_000)
            )
        )
        section = provider.build("EURUSD", Timeframe.M1).llm
        assert section.total_tokens == 2_000_000
        assert section.estimated_cost_usd == 0.75
    finally:
        store.close()


def test_cost_unknown_is_none() -> None:
    assert estimate_cost_usd("mystery", 100, 100) is None
    assert estimate_cost_usd("gpt-4o-mini", None, 5) is None
    assert estimate_cost_usd("llama3.1", 100, 100) == 0.0


def test_http_read_only_contract() -> None:
    provider, store = _provider()
    app = DashboardApp(provider, host="127.0.0.1", port=0)
    try:
        url = app.start()
        with urllib.request.urlopen(url + "/health", timeout=5) as response:
            assert json.loads(response.read()) == {"ok": True}
        with urllib.request.urlopen(url + "/api/state?symbol=EURUSD", timeout=5) as response:
            data = json.loads(response.read())
            assert data["account"]["balance"] == 1000.0
            assert data["market"]["symbol"] == "EURUSD"
        with urllib.request.urlopen(url + "/", timeout=5) as response:
            assert "read-only" in response.read().decode()
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            request = urllib.request.Request(url + "/api/state", method=method)
            try:
                urllib.request.urlopen(request, timeout=5)
            except urllib.error.HTTPError as exc:
                assert exc.code == 405
            else:
                raise AssertionError(f"{method} should be refused")
        request = urllib.request.Request(url + "/nope")
        try:
            urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("unknown path should 404")
        request = urllib.request.Request(url + "/api/state?timeframe=XX")
        try:
            urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
        else:
            raise AssertionError("bad timeframe should 400")
    finally:
        app.stop()
        store.close()
