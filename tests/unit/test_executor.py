"""Executor tests: lifecycle, guards, idempotency (FakeMT5, no terminal)."""

from __future__ import annotations

from collections import namedtuple
from datetime import UTC, datetime
from typing import Any

import pytest

from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.execution import ExecutionMode, ExecutionStatus
from mt5_agent.domain.planning import TradeAction, TradeProposal
from mt5_agent.execution.executor import MT5TradeExecutor
from mt5_agent.risk.result import ValidationResult
from mt5_agent.risk.supervisor import SupervisorDecision

TickTuple = namedtuple("TickTuple", ["time", "bid", "ask", "last", "volume", "time_msc"])
CheckResult = namedtuple("CheckResult", ["retcode", "comment"])
SendResult = namedtuple("SendResult", ["retcode", "order", "deal", "price", "comment"])


class FakeMT5:
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1

    def __init__(self) -> None:
        self.check_calls = 0
        self.send_calls = 0
        self.tick_calls = 0
        self.fail_check = False
        self.fail_send = False
        self.no_tick = False
        self.unverifiable = False

    def symbol_info_tick(self, symbol: str) -> Any:
        self.tick_calls += 1
        if self.no_tick:
            return None
        return TickTuple(1_700_000_000, 1.1000, 1.1002, 1.1001, 1.0, 1_700_000_000_000)

    def order_check(self, payload: dict[str, Any]) -> Any:
        self.check_calls += 1
        if self.fail_check:
            return CheckResult(10027, "no money")
        return CheckResult(10009, "ok")

    def order_send(self, payload: dict[str, Any]) -> Any:
        self.send_calls += 1
        if self.fail_send:
            return SendResult(10006, 0, 0, 0.0, "rejected")
        price = payload["price"] + 0.0001
        return SendResult(10009, 777, 888, price, "done")

    def positions_get(self, *args: Any, **kwargs: Any) -> Any:
        if self.unverifiable:
            return []
        ticket = kwargs.get("ticket", 0)
        return [object()] if ticket == 777 else []

    def last_error(self) -> Any:
        return (0, "ok")


class FakeConnection:
    def __init__(self, trade_mode: int = 0, connected: bool = True) -> None:
        self._account = AccountInfo(
            1,
            "S",
            "USD",
            10000.0,
            10000.0,
            0,
            10000.0,
            0,
            trade_allowed=True,
            trade_mode=trade_mode,
        )
        self._connected = connected

    def is_connected(self) -> bool:
        return self._connected

    def get_account_info(self) -> AccountInfo:
        return self._account


def _proposal(**kwargs: object) -> TradeProposal:
    base: dict[str, object] = {
        "action": TradeAction.BUY,
        "symbol": "EURUSD",
        "confidence": 0.7,
        "rationale": "test",
        "strategy": "s",
        "entry": 1.1,
        "stop_loss": 1.09,
        "take_profit": 1.12,
        "risk_pct": 0.5,
        "volume": 0.01,
    }
    base.update(kwargs)
    return TradeProposal(**base)  # type: ignore[arg-type]


def _approved(proposal: TradeProposal) -> SupervisorDecision:
    return SupervisorDecision(
        True, proposal, ValidationResult(True, ()), datetime(2026, 1, 1, tzinfo=UTC)
    )


def _rejected(proposal: TradeProposal) -> SupervisorDecision:
    from mt5_agent.risk.result import Violation, ViolationCode

    result = ValidationResult(False, (Violation(ViolationCode.COOLDOWN_ACTIVE, "cool"),))
    return SupervisorDecision(False, proposal, result, datetime(2026, 1, 1, tzinfo=UTC))


def test_dry_run_simulates_without_terminal_calls() -> None:
    fake = FakeMT5()
    executor = MT5TradeExecutor(mt5_module=fake, connection=FakeConnection())
    record = executor.execute(_approved(_proposal()), client_id="dry1")
    assert record.status == ExecutionStatus.SUCCESS
    assert fake.tick_calls == 0 and fake.send_calls == 0 and fake.check_calls == 0


def test_rejected_decision_never_executes() -> None:
    fake = FakeMT5()
    executor = MT5TradeExecutor(
        mode=ExecutionMode.DEMO, mt5_module=fake, connection=FakeConnection()
    )
    record = executor.execute(_rejected(_proposal()), client_id="rej1")
    assert record.status == ExecutionStatus.REJECTED
    assert "COOLDOWN_ACTIVE" in record.message
    assert fake.send_calls == 0


def test_hold_is_rejected() -> None:
    fake = FakeMT5()
    executor = MT5TradeExecutor(mt5_module=fake, connection=FakeConnection())
    hold = TradeProposal(TradeAction.HOLD, "EURUSD", 0.0, "wait", "s")
    record = executor.execute(_approved(hold), client_id="hold1")
    assert record.status == ExecutionStatus.REJECTED


def test_live_blocked_by_default() -> None:
    fake = FakeMT5()
    executor = MT5TradeExecutor(
        mode=ExecutionMode.LIVE, mt5_module=fake, connection=FakeConnection()
    )
    record = executor.execute(_approved(_proposal()), client_id="live1")
    assert record.status == ExecutionStatus.REJECTED
    assert fake.send_calls == 0


def test_demo_success_verified() -> None:
    fake = FakeMT5()
    executor = MT5TradeExecutor(
        mode=ExecutionMode.DEMO, mt5_module=fake, connection=FakeConnection(trade_mode=0)
    )
    record = executor.execute(_approved(_proposal()), client_id="demo1")
    assert record.status == ExecutionStatus.SUCCESS
    assert record.ticket == 777 and record.deal == 888
    assert record.slippage == pytest.approx(0.0001)
    assert record.message == "verified fill"


def test_demo_refused_on_real_account() -> None:
    fake = FakeMT5()
    executor = MT5TradeExecutor(
        mode=ExecutionMode.DEMO, mt5_module=fake, connection=FakeConnection(trade_mode=2)
    )
    record = executor.execute(_approved(_proposal()), client_id="real1")
    assert record.status == ExecutionStatus.REJECTED
    assert fake.send_calls == 0


def test_check_failure_records_code() -> None:
    fake = FakeMT5()
    fake.fail_check = True
    executor = MT5TradeExecutor(
        mode=ExecutionMode.DEMO, mt5_module=fake, connection=FakeConnection()
    )
    record = executor.execute(_approved(_proposal()), client_id="chk1")
    assert record.status == ExecutionStatus.FAILED
    assert record.error_code == "10027"


def test_send_failure_records_code() -> None:
    fake = FakeMT5()
    fake.fail_send = True
    executor = MT5TradeExecutor(
        mode=ExecutionMode.DEMO, mt5_module=fake, connection=FakeConnection()
    )
    record = executor.execute(_approved(_proposal()), client_id="snd1")
    assert record.status == ExecutionStatus.FAILED
    assert record.error_code == "10006"


def test_idempotent_retry_never_resends() -> None:
    fake = FakeMT5()
    executor = MT5TradeExecutor(
        mode=ExecutionMode.DEMO, mt5_module=fake, connection=FakeConnection()
    )
    first = executor.execute(_approved(_proposal()), client_id="idem1")
    second = executor.execute(_approved(_proposal()), client_id="idem1")
    assert first is second
    assert fake.send_calls == 1
    assert len(executor.ledger) == 1


def test_disconnected_and_missing_tick_fail() -> None:
    fake = FakeMT5()
    offline = MT5TradeExecutor(
        mode=ExecutionMode.DEMO, mt5_module=fake, connection=FakeConnection(connected=False)
    )
    assert (
        offline.execute(_approved(_proposal()), client_id="off1").status == ExecutionStatus.FAILED
    )
    fake2 = FakeMT5()
    fake2.no_tick = True
    no_tick = MT5TradeExecutor(
        mode=ExecutionMode.DEMO, mt5_module=fake2, connection=FakeConnection()
    )
    record = no_tick.execute(_approved(_proposal()), client_id="tick1")
    assert record.status == ExecutionStatus.FAILED
    assert "no tick" in record.message


def test_unverified_fill_stays_success() -> None:
    fake = FakeMT5()
    fake.unverifiable = True
    executor = MT5TradeExecutor(
        mode=ExecutionMode.DEMO, mt5_module=fake, connection=FakeConnection()
    )
    record = executor.execute(_approved(_proposal()), client_id="unv1")
    assert record.status == ExecutionStatus.SUCCESS
    assert "assumed" in record.message
