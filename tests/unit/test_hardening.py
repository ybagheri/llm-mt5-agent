"""Phase 12 hardening tests (fakes only; no MT5 terminal, LLM, or network)."""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from mt5_agent.ai.errors import LLMTimeoutError
from mt5_agent.ai.models import LLMRequest, LLMResponse
from mt5_agent.ai.planner import LLMPlanner
from mt5_agent.ai.provider import LLMProvider
from mt5_agent.application.account_service import AccountService
from mt5_agent.application.agent import ContextBuilder, Observer, TradingAgent
from mt5_agent.application.connection_service import ConnectionService, RetryPolicy
from mt5_agent.application.health import (
    ComponentHealth,
    HealthService,
    HealthStatus,
    SystemHealth,
    overall,
)
from mt5_agent.application.market_service import MarketService
from mt5_agent.application.order_service import OrderService
from mt5_agent.application.position_service import PositionService
from mt5_agent.application.strategy_service import StrategyService
from mt5_agent.application.watchdog import Watchdog, WatchdogConfig
from mt5_agent.config.settings import AppSettings
from mt5_agent.dashboard.app import DashboardApp, is_loopback
from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.agent import Stage, StageStatus
from mt5_agent.domain.errors import MT5ConnectionError
from mt5_agent.domain.execution import ExecutionMode, ExecutionStatus
from mt5_agent.domain.market import Candle, MarketSnapshot, SymbolInfo, Tick, Timeframe
from mt5_agent.domain.planning import PlannerInput, TradeAction, TradeProposal
from mt5_agent.domain.ports import MT5ConnectionPort
from mt5_agent.domain.terminal import (
    ConnectionConfig,
    ConnectionHealth,
    MT5Credentials,
    TerminalInfo,
)
from mt5_agent.execution.executor import MT5TradeExecutor
from mt5_agent.logging_utils import audit, configure_logging, get_logger, scrub_message, scrub_value
from mt5_agent.memory.memories import (
    ShortTermMemory,
    StrategyMemory,
    TradeMemory,
    WorldMemory,
)
from mt5_agent.memory.sqlite_store import SQLiteMemoryStore
from mt5_agent.risk.config import RiskConfig
from mt5_agent.risk.result import ValidationResult
from mt5_agent.risk.supervisor import Supervisor, SupervisorDecision
from mt5_agent.strategies.null_strategy import NullStrategy

# -- secret scrubbing ------------------------------------------------------


def test_scrub_value_redacts_nested_secrets() -> None:
    data = {
        "symbol": "EURUSD",
        "api_key": "sk-live",
        "nested": {"password": "hunter2", "login": 123},
        "items": [{"token": "abc"}, " Bearer xyz123 "],
    }
    scrubbed = scrub_value(data)
    assert scrubbed["symbol"] == "EURUSD"
    assert scrubbed["api_key"] == "***"
    assert scrubbed["nested"] == {"password": "***", "login": "***"}
    assert scrubbed["items"][0] == {"token": "***"}
    # original must be untouched
    assert data["api_key"] == "sk-live"


def test_scrub_message_redacts_inline_secrets() -> None:
    assert scrub_message("api_key=sk-live retry") == "api_key=*** retry"
    assert scrub_message("using Bearer abcDEF123.token ok") == "using Bearer *** ok"
    assert scrub_message("plain message") == "plain message"


def test_json_log_output_never_carries_secrets(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", log_format="json", force=True)
    logger = get_logger("test.secrets")
    logger.info(
        "provider call",
        extra={"extra_fields": {"llm_api_key": "sk-live", "symbol": "EURUSD"}},
    )
    record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert record["llm_api_key"] == "***"
    assert record["symbol"] == "EURUSD"


def test_audit_event_is_structured(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", log_format="json", force=True)
    audit(get_logger("test.audit"), "order_submitted", symbol="EURUSD", password="x")
    record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert record["audit_event"] == "order_submitted"
    assert record["symbol"] == "EURUSD"
    assert record["password"] == "***"  # noqa: S105 - asserts scrubbed placeholder


# -- health ----------------------------------------------------------------


def _comp(name: str, status: HealthStatus) -> ComponentHealth:
    return ComponentHealth(name, status, name)


def test_overall_aggregation() -> None:
    assert overall((_comp("a", HealthStatus.HEALTHY),)) == HealthStatus.HEALTHY
    assert (
        overall((_comp("a", HealthStatus.HEALTHY), _comp("b", HealthStatus.DEGRADED)))
        == HealthStatus.DEGRADED
    )
    assert (
        overall((_comp("a", HealthStatus.DEGRADED), _comp("b", HealthStatus.UNHEALTHY)))
        == HealthStatus.UNHEALTHY
    )
    assert overall(()) == HealthStatus.UNHEALTHY  # nothing verified: not healthy


def test_health_service_check_and_probe_failure() -> None:
    def boom() -> ComponentHealth:
        raise RuntimeError("probe exploded")

    service = HealthService({"ok": lambda: _comp("ok", HealthStatus.HEALTHY), "bad": boom})
    assert service.probe_names == ("ok", "bad")
    health = service.check()
    assert isinstance(health, SystemHealth)
    assert health.status == HealthStatus.UNHEALTHY
    assert health.healthy is False
    payload = health.to_dict()
    assert payload["status"] == "UNHEALTHY"
    assert payload["components"]["bad"]["status"] == "UNHEALTHY"
    assert "checked_at" in payload


# -- retry / reconnect ------------------------------------------------------


def test_retry_backoff_schedule() -> None:
    fixed = RetryPolicy(max_attempts=3, delay_seconds=2.0)
    assert fixed.delay_for(1) == 2.0
    assert fixed.delay_for(3) == 2.0
    backoff = RetryPolicy(max_attempts=4, delay_seconds=1.0, backoff_factor=2.0)
    assert [backoff.delay_for(a) for a in (1, 2, 3)] == [1.0, 2.0, 4.0]
    capped = RetryPolicy(
        max_attempts=4, delay_seconds=1.0, backoff_factor=3.0, max_delay_seconds=5.0
    )
    assert capped.delay_for(3) == 5.0
    with pytest.raises(ValueError):
        RetryPolicy(backoff_factor=0.5)
    with pytest.raises(ValueError):
        backoff.delay_for(0)


class _FlakyPort(MT5ConnectionPort):
    """MT5ConnectionPort double with scripted connect failures."""

    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.connected = False

    def connect(self, config: ConnectionConfig, credentials: MT5Credentials | None = None) -> None:
        self.connect_calls += 1
        if self.connect_calls <= self.failures:
            raise MT5ConnectionError("boom")
        self.connected = True

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    def get_account_info(self) -> AccountInfo:
        return AccountInfo(1, "S", "USD", 1.0, 1.0, 0.0, 1.0, 0.0)

    def get_terminal_info(self) -> TerminalInfo:
        return TerminalInfo(connected=True, trade_allowed=True)

    def check_health(self) -> ConnectionHealth:
        return ConnectionHealth(connected=self.connected, trade_allowed=True)


def test_reconnect_runs_post_connect_verification() -> None:
    port = _FlakyPort()
    service = ConnectionService(port, RetryPolicy(max_attempts=1, delay_seconds=0))
    seen: list[str] = []
    health = service.reconnect(
        ConnectionConfig(), verify=lambda: seen.append("account+positions+orders")
    )
    assert health.connected is True
    assert port.disconnect_calls == 1
    assert seen == ["account+positions+orders"]


def test_reconnect_verify_failure_blocks_trading() -> None:
    port = _FlakyPort()
    service = ConnectionService(port, RetryPolicy(max_attempts=1, delay_seconds=0))

    def stale() -> None:
        raise RuntimeError("positions changed during outage")

    with pytest.raises(RuntimeError, match="positions changed"):
        service.reconnect(ConnectionConfig(), verify=stale)


# -- execution idempotency / UNKNOWN ----------------------------------------


def _proposal() -> TradeProposal:
    return TradeProposal(
        TradeAction.BUY,
        "EURUSD",
        0.7,
        "test",
        "s",
        entry=1.1,
        stop_loss=1.09,
        take_profit=1.12,
        risk_pct=0.5,
        volume=0.01,
    )


def _approved(proposal: TradeProposal) -> SupervisorDecision:
    return SupervisorDecision(
        True, proposal, ValidationResult(True, ()), datetime(2026, 1, 1, tzinfo=UTC)
    )


class _TimeoutMT5:
    """Fake terminal that times out after submission (ambiguous outcome)."""

    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    send_calls = 0

    def symbol_info_tick(self, symbol: str) -> Any:
        from collections import namedtuple

        tick = namedtuple("Tick", ["ask", "bid"])(1.1002, 1.1000)
        return tick

    def order_check(self, payload: dict[str, Any]) -> Any:
        from collections import namedtuple

        return namedtuple("Check", ["retcode", "comment"])(10009, "ok")

    def order_send(self, payload: dict[str, Any]) -> Any:
        type(self).send_calls += 1
        raise TimeoutError("send timed out after 30s")

    def last_error(self) -> Any:
        return (0, "ok")


class _OfflineConnection:
    def is_connected(self) -> bool:
        return False

    def get_account_info(self) -> AccountInfo:
        return AccountInfo(1, "S", "USD", 1.0, 1.0, 0.0, 1.0, 0.0)


def test_execution_timeout_is_unknown_not_failed() -> None:
    _TimeoutMT5.send_calls = 0

    class DemoConnection:
        def is_connected(self) -> bool:
            return True

        def get_account_info(self) -> AccountInfo:
            return AccountInfo(1, "S", "USD", 1.0, 1.0, 0.0, 1.0, 0.0, trade_mode=0)

    executor = MT5TradeExecutor(
        mode=ExecutionMode.DEMO,
        mt5_module=_TimeoutMT5(),
        connection=DemoConnection(),  # type: ignore[arg-type]
    )
    record = executor.execute(_approved(_proposal()), client_id="ambiguous1")
    assert record.status == ExecutionStatus.UNKNOWN
    assert "same client_id" in record.message
    # Retry with the same id replays from the ledger instead of resending.
    replayed = executor.execute(_approved(_proposal()), client_id="ambiguous1")
    assert replayed is record
    assert _TimeoutMT5.send_calls == 1


def test_disconnected_execution_guides_safe_retry() -> None:
    from collections import namedtuple

    tick = namedtuple("Tick", ["ask", "bid"])(1.1002, 1.1000)

    class FakeMT5:
        TRADE_ACTION_DEAL = 1
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        ORDER_TIME_GTC = 0
        ORDER_FILLING_IOC = 1

        def symbol_info_tick(self, symbol: str) -> Any:
            return tick

    executor = MT5TradeExecutor(
        mode=ExecutionMode.DEMO,
        mt5_module=FakeMT5(),
        connection=_OfflineConnection(),  # type: ignore[arg-type]
    )
    record = executor.execute(_approved(_proposal()), client_id="offline1")
    assert record.status == ExecutionStatus.FAILED
    assert "same client_id" in record.message


# -- LLM failure -> HOLD -----------------------------------------------------


class _TimeoutProvider(LLMProvider):
    name = "timeout-fake"

    @property
    def model(self) -> str:
        return "fake-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        raise LLMTimeoutError("timed out", provider="timeout-fake")


def _planner_input() -> PlannerInput:
    from mt5_agent.domain.strategy import Direction, Setup, StrategySignal

    now = datetime(2026, 1, 1, tzinfo=UTC)
    candle = Candle("EURUSD", Timeframe.M1, now, 1.0, 1.2, 0.9, 1.15)
    snap = MarketSnapshot("EURUSD", Timeframe.M1, now, candles=(candle,))
    setup = Setup("d:breakout:long", "StructureBreakout", Direction.LONG, 0.6)
    signal = StrategySignal(
        "donchian_breakout",
        "EURUSD",
        Timeframe.M1,
        Direction.LONG,
        0.6,
        (setup,),
        {"prior_high": 1.1},
        "break",
        now,
    )
    return PlannerInput("EURUSD", Timeframe.M1, snap, signal)


def test_llm_timeout_degrades_to_hold() -> None:
    proposal = LLMPlanner(_TimeoutProvider()).plan(_planner_input())
    assert proposal.action == TradeAction.HOLD
    assert proposal.confidence == 0.0


# -- watchdog ----------------------------------------------------------------


def test_watchdog_trips_and_halts_only() -> None:
    watchdog = Watchdog(WatchdogConfig(max_consecutive_failures=2, stale_after_s=0))
    assert watchdog.status() == HealthStatus.HEALTHY
    assert watchdog.should_halt() is False
    watchdog.note_failure("cycle", "feed down")
    watchdog.note_failure("cycle", "feed down")
    assert watchdog.status() == HealthStatus.UNHEALTHY
    assert watchdog.should_halt() is True
    assert watchdog.snapshot()["halt"] is True
    watchdog.note_success("cycle")  # success alone does not untrip a latched halt
    assert watchdog.should_halt() is True
    watchdog.reset()
    assert watchdog.should_halt() is False


def test_watchdog_stale_market_data_degrades() -> None:
    watchdog = Watchdog(WatchdogConfig(max_consecutive_failures=5, stale_after_s=60.0))
    watchdog.note_observation(datetime.now(UTC) - timedelta(seconds=3600))
    assert watchdog.status() == HealthStatus.DEGRADED
    assert watchdog.should_halt() is False  # degraded never halts by itself


def test_watchdog_config_validation() -> None:
    with pytest.raises(ValueError):
        WatchdogConfig(max_consecutive_failures=0)
    with pytest.raises(ValueError):
        WatchdogConfig(stale_after_s=-1.0)


# -- agent + watchdog integration --------------------------------------------


def _snapshot(symbol: str = "EURUSD") -> MarketSnapshot:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    candle = Candle(symbol, Timeframe.M1, now, 1.0, 1.1, 0.9, 1.05)
    tick = Tick(symbol, now, 1.04, 1.06)
    return MarketSnapshot(symbol, Timeframe.M1, now, candles=(candle,), tick=tick)


class _MarketPort:
    def get_tick(self, symbol: str) -> Tick:
        return _snapshot(symbol).tick  # type: ignore[return-value]

    def get_candles(
        self, symbol: str, timeframe: Timeframe, count: int = 100, start_pos: int = 0
    ) -> list[Candle]:
        return list(_snapshot(symbol).candles)

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        return SymbolInfo(symbol, point=0.00001, digits=5)

    def get_snapshot(self, symbol: str, timeframe: Timeframe, count: int = 100) -> MarketSnapshot:
        return _snapshot(symbol)


class _BoomMarket(_MarketPort):
    def get_snapshot(self, symbol: str, timeframe: Timeframe, count: int = 100) -> MarketSnapshot:
        raise RuntimeError("feed down")


class _Conn:
    def connect(self, config: Any, credentials: Any = None) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def is_connected(self) -> bool:
        return True

    def get_account_info(self) -> AccountInfo:
        return AccountInfo(1, "S", "USD", 10000.0, 10000.0, 0, 10000.0, 0)

    def get_terminal_info(self) -> TerminalInfo:
        return TerminalInfo(connected=True, trade_allowed=True)

    def check_health(self) -> ConnectionHealth:
        return ConnectionHealth(True)


class _Empty:
    def get_open_positions(self, symbol: str | None = None) -> list[Any]:
        return []

    def get_pending_orders(self, symbol: str | None = None) -> list[Any]:
        return []


def _agent(watchdog: Watchdog | None, market_port: Any = None) -> TradingAgent:
    store = SQLiteMemoryStore(":memory:")
    market = MarketService(market_port or _MarketPort())
    conn = _Conn()
    observer = Observer(
        market,
        AccountService(conn, _Empty(), _Empty()),  # type: ignore[arg-type]
        PositionService(_Empty()),
        OrderService(_Empty()),
    )  # type: ignore[arg-type]
    builder = ContextBuilder(
        StrategyService([NullStrategy()]),
        StrategyMemory(store),
        TradeMemory(store),
    )
    return TradingAgent(
        observer=observer,
        context_builder=builder,
        planner=None,
        supervisor=Supervisor(config=RiskConfig()),
        executor=MT5TradeExecutor(),
        short_term=ShortTermMemory(store),
        trade_memory=TradeMemory(store),
        strategy_memory=StrategyMemory(store),
        world_memory=WorldMemory(store),
        watchdog=watchdog,
    )


def test_agent_halts_loop_after_repeated_failures() -> None:
    watchdog = Watchdog(WatchdogConfig(max_consecutive_failures=2, stale_after_s=0))
    agent = _agent(watchdog, _BoomMarket())
    cycles = agent.run(["EURUSD"], Timeframe.M1, interval_s=0, max_cycles=5)
    assert 1 <= len(cycles) <= 3  # loop stops once the watchdog trips
    assert watchdog.should_halt() is True
    refused = agent.run_cycle("EURUSD", Timeframe.M1)
    assert refused.stage(Stage.OBSERVE) is not None
    assert refused.stage(Stage.OBSERVE).status == StageStatus.SKIPPED


def test_agent_records_watchdog_success_on_ok_cycle() -> None:
    watchdog = Watchdog(WatchdogConfig(max_consecutive_failures=5, stale_after_s=0))
    agent = _agent(watchdog)
    cycle = agent.run_cycle("EURUSD", Timeframe.M1)
    assert cycle.ok is True
    assert watchdog.should_halt() is False
    assert watchdog.snapshot()["totals"]["success"] >= 1


def test_graceful_stop_is_idempotent() -> None:
    agent = _agent(None)
    agent.stop()
    agent.stop()  # must not raise
    assert agent.run(["EURUSD"], Timeframe.M1, interval_s=0, max_cycles=1) == []


# -- dashboard hardening -----------------------------------------------------


def _dashboard_app(**kwargs: Any) -> tuple[DashboardApp, SQLiteMemoryStore]:
    from mt5_agent.dashboard.provider import DashboardStateProvider

    store = SQLiteMemoryStore(":memory:")
    market = MarketService(_MarketPort())
    conn = _Conn()
    provider = DashboardStateProvider(
        market=market,
        account=AccountService(conn, _Empty(), _Empty()),  # type: ignore[arg-type]
        positions=PositionService(_Empty()),  # type: ignore[arg-type]
        orders=OrderService(_Empty()),  # type: ignore[arg-type]
        strategies=StrategyService([NullStrategy()]),
        risk_config=RiskConfig(),
        version="0.0",
        trading_mode="dry_run",
    )
    return DashboardApp(provider, host="127.0.0.1", port=0, **kwargs), store


def test_api_health_endpoint() -> None:
    app, store = _dashboard_app(
        health_provider=lambda: SystemHealth(
            HealthStatus.DEGRADED, (_comp("llm", HealthStatus.DEGRADED),)
        ).to_dict()
    )
    try:
        url = app.start()
        with urllib.request.urlopen(url + "/api/health", timeout=5) as response:
            data = json.loads(response.read())
        assert data["status"] == "DEGRADED"
        assert data["healthy"] is False
        # liveness endpoint keeps its exact contract
        with urllib.request.urlopen(url + "/health", timeout=5) as response:
            assert json.loads(response.read()) == {"ok": True}
    finally:
        app.stop()
        app.stop()  # idempotent shutdown
        store.close()


def test_api_health_without_provider_is_unknown() -> None:
    app, store = _dashboard_app()
    try:
        url = app.start()
        with urllib.request.urlopen(url + "/api/health", timeout=5) as response:
            assert json.loads(response.read())["status"] == "UNKNOWN"
    finally:
        app.stop()
        store.close()


def test_loopback_detection() -> None:
    assert is_loopback("127.0.0.1") is True
    assert is_loopback("127.0.0.5") is True
    assert is_loopback("localhost") is True
    assert is_loopback("0.0.0.0") is False  # noqa: S104 (string literal, never bound)
    assert is_loopback("192.168.1.10") is False


# -- configuration safety ----------------------------------------------------


def test_watchdog_settings_defaults_and_validation() -> None:
    settings = AppSettings()
    assert settings.watchdog_max_consecutive_failures == 5
    assert settings.watchdog_stale_after_s == 300.0
    with pytest.raises(ValueError):
        AppSettings(watchdog_max_consecutive_failures=0)
    # demo-first invariant still holds alongside the new settings
    assert settings.trading_mode == "dry_run"
    with pytest.raises(ValueError, match="Live trading is never enabled"):
        AppSettings(trading_mode="live", enable_live_trading=False)


def test_live_gate_rejects_demo_bypass() -> None:
    with pytest.raises(ValueError, match="Live trading is never enabled"):
        AppSettings(execution_mode="live", enable_live_trading=False)


def test_logging_setup_is_idempotent(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", log_format="json", force=True)
    audit(get_logger("test.idempotent"), "shutdown", reason="test")
    # reconfiguring must keep emitting valid audit records (no handler pile-up crash)
    configure_logging(level="INFO", log_format="json", force=True)
    audit(get_logger("test.idempotent"), "shutdown", reason="retest")
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["audit_event"] == "shutdown" for line in lines)
