"""Execution model tests (validation only)."""

from __future__ import annotations

import pytest

from mt5_agent.domain.execution import (
    ExecutionMode,
    ExecutionRecord,
    ExecutionStatus,
    OrderRequest,
)
from mt5_agent.domain.planning import TradeAction


def _request(**kwargs: object) -> OrderRequest:
    base: dict[str, object] = {"symbol": "EURUSD", "action": TradeAction.BUY, "volume": 0.01}
    base.update(kwargs)
    return OrderRequest(**base)  # type: ignore[arg-type]


def test_request_validation() -> None:
    with pytest.raises(ValueError):
        _request(action=TradeAction.HOLD)
    with pytest.raises(ValueError):
        _request(volume=0.0)
    with pytest.raises(ValueError):
        _request(symbol="  ")
    assert _request().client_id != ""


def test_record_success_requires_ticket_outside_dry_run() -> None:
    with pytest.raises(ValueError):
        ExecutionRecord(
            "c", "EURUSD", TradeAction.BUY, 0.01, ExecutionStatus.SUCCESS, ExecutionMode.DEMO
        )
    dry = ExecutionRecord(
        "c",
        "EURUSD",
        TradeAction.BUY,
        0.01,
        ExecutionStatus.SUCCESS,
        ExecutionMode.DRY_RUN,
        message="simulated",
    )
    assert dry.ticket is None
