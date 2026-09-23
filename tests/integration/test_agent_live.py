"""Live agent-cycle integration test (read-only + DRY_RUN, skipped by default).

Run with: MT5_AGENT_RUN_LIVE_MT5_TESTS=true pytest tests/integration/ -q
"""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("MT5_AGENT_RUN_LIVE_MT5_TESTS", "false").lower() != "true",
        reason="live MT5 terminal not requested",
    ),
]


def test_live_agent_cycle_dry_run() -> None:
    from mt5_agent.application.account_service import AccountService
    from mt5_agent.application.agent import ContextBuilder, Observer, TradingAgent
    from mt5_agent.application.connection_service import ConnectionService, RetryPolicy
    from mt5_agent.application.market_service import MarketService
    from mt5_agent.application.order_service import OrderService
    from mt5_agent.application.position_service import PositionService
    from mt5_agent.application.strategy_service import StrategyService
    from mt5_agent.config.loader import load_settings
    from mt5_agent.domain.execution import ExecutionMode
    from mt5_agent.domain.market import Timeframe
    from mt5_agent.execution.executor import MT5TradeExecutor
    from mt5_agent.infrastructure.mt5.connection_adapter import MT5ConnectionAdapter
    from mt5_agent.infrastructure.mt5.market_adapter import MT5MarketDataAdapter
    from mt5_agent.infrastructure.mt5.trading_adapter import MT5TradingDataAdapter
    from mt5_agent.memory.memories import (
        ShortTermMemory,
        StrategyMemory,
        TradeMemory,
        WorldMemory,
    )
    from mt5_agent.memory.sqlite_store import SQLiteMemoryStore
    from mt5_agent.risk.supervisor import Supervisor
    from mt5_agent.strategies.measure_move import DonchianBreakoutStrategy
    from mt5_agent.strategies.null_strategy import NullStrategy

    settings = load_settings()
    conn = MT5ConnectionAdapter()
    svc = ConnectionService(conn, RetryPolicy(max_attempts=1, delay_seconds=0))
    try:
        svc.ensure_connected(settings.to_connection_config())
    except Exception as exc:
        pytest.skip(f"MT5 terminal unavailable: {exc}")
        return
    store = SQLiteMemoryStore(":memory:")
    try:
        market = MarketService(MT5MarketDataAdapter(connection=conn))
        trading = MT5TradingDataAdapter(connection=conn)
        account = AccountService(conn, trading, trading)
        observer = Observer(market, account, PositionService(trading), OrderService(trading))
        builder = ContextBuilder(
            StrategyService([NullStrategy(), DonchianBreakoutStrategy()]),
            StrategyMemory(store),
            TradeMemory(store),
        )
        agent = TradingAgent(
            observer=observer,
            context_builder=builder,
            planner=None,
            supervisor=Supervisor(config=settings.to_risk_config()),
            executor=MT5TradeExecutor(mode=ExecutionMode.DRY_RUN, connection=conn),
            short_term=ShortTermMemory(store),
            trade_memory=TradeMemory(store),
            strategy_memory=StrategyMemory(store),
            world_memory=WorldMemory(store),
        )
        cycle = agent.run_cycle(settings.mt5_default_symbol, Timeframe.M1)
        assert cycle.ok is True
        assert cycle.stage(cycle.stages[0].stage) is not None
        assert len(cycle.stages) == 9
    finally:
        store.close()
        svc.disconnect()
