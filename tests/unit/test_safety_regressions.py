from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from mt5_agent.application.account_service import AccountService
from mt5_agent.config.settings import AppSettings
from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.trading import AccountState, Deal, Position, PositionSide


class Connection:
    def get_account_info(self) -> AccountInfo:
        return AccountInfo(1, "Demo", "USD", 1000.0, 1000.0, 0.0, 1000.0, 0.0)


class Positions:
    def get_open_positions(self, symbol: str | None = None) -> list[Position]:
        return [
            Position(1, "EURUSD", PositionSide.BUY, 0.1, 1.0, 1.0),
            Position(2, "XAUUSD", PositionSide.SELL, 0.2, 2000.0, 2000.0),
        ]


class Orders:
    def get_pending_orders(self, symbol: str | None = None) -> list[Any]:
        return []


class History:
    def get_deals(self, date_from: datetime, date_to: datetime) -> list[Deal]:
        return [
            Deal(
                1,
                1,
                1,
                "EURUSD",
                1,
                0,
                0.1,
                1.0,
                profit=5.0,
                commission=-1.0,
                time=date_from,
            )
        ]

    def get_history_orders(self, date_from: datetime, date_to: datetime) -> list[Any]:
        return []


def test_account_state_is_account_wide_and_keeps_day_pnl() -> None:
    state = AccountService(Connection(), Positions(), Orders(), History()).get_state()
    assert isinstance(state, AccountState)
    assert state.open_positions == 2
    assert state.exposure_volume == pytest.approx(0.3)
    assert state.day_realized_pnl == pytest.approx(4.0)


def test_explicit_missing_config_fails_closed(tmp_path: Any) -> None:
    from mt5_agent.config.loader import load_settings

    with pytest.raises(FileNotFoundError):
        load_settings(tmp_path / "missing.yaml", load_env_file=False)


def test_modes_cannot_disagree() -> None:
    with pytest.raises(ValueError, match="must match"):
        AppSettings(trading_mode="dry_run", execution_mode="demo")
    with pytest.raises(ValueError, match="must match"):
        AppSettings(trading_mode="demo", execution_mode="dry_run")


def test_demo_connection_is_mandatory() -> None:
    from mt5_agent.domain.execution import ExecutionMode
    from mt5_agent.domain.planning import TradeAction, TradeProposal
    from mt5_agent.execution.executor import MT5TradeExecutor
    from mt5_agent.risk.result import ValidationResult
    from mt5_agent.risk.supervisor import SupervisorDecision

    proposal = TradeProposal(
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
    decision = SupervisorDecision(True, proposal, ValidationResult(True, ()), datetime.now(UTC))
    record = MT5TradeExecutor(mode=ExecutionMode.DEMO).execute(decision, client_id="guard")
    assert record.status.value == "REJECTED"
    assert "verified MT5 connection" in record.message
