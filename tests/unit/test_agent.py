"""Agent orchestrator tests (fake ports; DRY_RUN executor; :memory: store)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from mt5_agent.application.account_service import AccountService
from mt5_agent.application.agent import ContextBuilder, Observer, TradingAgent
from mt5_agent.application.market_service import MarketService
from mt5_agent.application.order_service import OrderService
from mt5_agent.application.position_service import PositionService
from mt5_agent.application.strategy_service import StrategyService
from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.agent import Stage, StageStatus
from mt5_agent.domain.market import Candle, MarketSnapshot, SymbolInfo, Tick, Timeframe
from mt5_agent.domain.planning import TradeAction
from mt5_agent.domain.terminal import ConnectionHealth, TerminalInfo
from mt5_agent.execution.executor import MT5TradeExecutor
from mt5_agent.memory.memories import (
    ShortTermMemory,
    StrategyMemory,
    TradeMemory,
    WorldMemory,
)
from mt5_agent.memory.sqlite_store import SQLiteMemoryStore
from mt5_agent.risk.config import RiskConfig
from mt5_agent.risk.supervisor import Supervisor
from mt5_agent.strategies.null_strategy import NullStrategy


def _snapshot(symbol: str = "EURUSD") -> MarketSnapshot:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    candle = Candle(symbol, Timeframe.M1, now, 1.0, 1.1, 0.9, 1.05)
    tick = Tick(symbol, now, 1.04, 1.06)
    return MarketSnapshot(symbol, Timeframe.M1, now, candles=(candle,), tick=tick)


class FakeMarketPort:
    def __init__(self, snapshot: MarketSnapshot | None = None) -> None:
        self._snapshot = snapshot or _snapshot()
        self.calls = 0

    def get_tick(self, symbol: str) -> Tick:
        raise AssertionError("unused in cycle")

    def get_candles(
        self, symbol: str, timeframe: Timeframe, count: int = 100, start_pos: int = 0
    ) -> list[Candle]:
        raise AssertionError("unused in cycle")

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        raise AssertionError("unused in cycle")

    def get_snapshot(self, symbol: str, timeframe: Timeframe, count: int = 100) -> MarketSnapshot:
        self.calls += 1
        return self._snapshot


class FakeConnection:
    def __init__(self) -> None:
        self.calls = 0

    def connect(self, config: Any, credentials: Any = None) -> None:
        self.calls += 1

    def disconnect(self) -> None:
        pass

    def is_connected(self) -> bool:
        return True

    def get_account_info(self) -> AccountInfo:
        return AccountInfo(1, "S", "USD", 10000.0, 10000.0, 0, 10000.0, 0, trade_allowed=True)

    def get_terminal_info(self) -> TerminalInfo:
        return TerminalInfo(connected=True, trade_allowed=True)

    def check_health(self) -> ConnectionHealth:
        return ConnectionHealth(True)


class FakePositions:
    def get_open_positions(self, symbol: str | None = None) -> list[Any]:
        return []


class FakeOrders:
    def get_pending_orders(self, symbol: str | None = None) -> list[Any]:
        return []


class BoomMarket(FakeMarketPort):
    def get_snapshot(self, symbol: str, timeframe: Timeframe, count: int = 100) -> MarketSnapshot:
        raise RuntimeError("feed down")


def _agent(**overrides: Any) -> tuple[TradingAgent, SQLiteMemoryStore]:
    store = SQLiteMemoryStore(":memory:")
    market = MarketService(overrides.get("market_port", FakeMarketPort()))
    conn = FakeConnection()
    positions = PositionService(FakePositions())
    orders = OrderService(FakeOrders())
    account = AccountService(conn, FakePositions(), FakeOrders())
    observer = Observer(market, account, positions, orders)
    strategies = StrategyService([NullStrategy()])
    memories = {
        "strategy_memory": StrategyMemory(store),
        "trade_memory": TradeMemory(store),
    }
    builder = ContextBuilder(strategies, **memories)
    agent = TradingAgent(
        observer=observer,
        context_builder=builder,
        planner=None,
        supervisor=Supervisor(config=RiskConfig()),
        executor=MT5TradeExecutor(),
        short_term=ShortTermMemory(store),
        trade_memory=memories["trade_memory"],
        strategy_memory=memories["strategy_memory"],
        world_memory=WorldMemory(store),
    )
    return agent, store


def test_full_cycle_hold_path() -> None:
    agent, store = _agent()
    try:
        cycle = agent.run_cycle("EURUSD", Timeframe.M1)
        assert cycle.ok is True
        assert [s.stage for s in cycle.stages] == list(Stage)
        assert cycle.stage(Stage.PLAN).summary.startswith("HOLD")
        assert cycle.stage(Stage.SUPERVISE).summary == "approved"
        assert cycle.stage(Stage.EXECUTE).status == StageStatus.SKIPPED
        assert cycle.stage(Stage.VERIFY).status == StageStatus.SKIPPED
        assert TradeMemory(store).count() >= 2  # proposal + decision
        assert ShortTermMemory(store).count() == 1
    finally:
        store.close()


def test_observe_failure_degrades() -> None:
    agent, store = _agent(market_port=BoomMarket())
    try:
        cycle = agent.run_cycle("EURUSD", Timeframe.M1)
        assert cycle.ok is False
        assert cycle.stage(Stage.OBSERVE).status == StageStatus.FAILED
        assert cycle.stage(Stage.PLAN) is None  # pipeline halted safely
        assert cycle.error == ""
    finally:
        store.close()


def test_run_loop_max_cycles_and_stop() -> None:
    agent, store = _agent()
    try:
        cycles = agent.run(["EURUSD"], Timeframe.M1, interval_s=0, max_cycles=2)
        assert len(cycles) == 2
        assert agent.cycles_completed == 2
        agent.stop()
        assert agent.run(["EURUSD"], Timeframe.M1, interval_s=0, max_cycles=5) == []
    finally:
        store.close()


def test_agent_symbol_list_parsing() -> None:
    from mt5_agent.config.settings import AppSettings

    assert AppSettings(agent_symbols="EURUSD, XAUUSD").agent_symbol_list() == ["EURUSD", "XAUUSD"]
    try:
        AppSettings(agent_symbols="  ").agent_symbol_list()
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_proposal_action_enum_available() -> None:
    assert TradeAction.HOLD.value == "HOLD"
