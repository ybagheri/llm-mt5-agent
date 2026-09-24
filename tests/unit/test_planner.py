"""LLMPlanner tests (fake providers; asserts validation + HOLD fallback)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from mt5_agent.ai.errors import LLMProviderError
from mt5_agent.ai.models import LLMRequest, LLMResponse, LLMUsage
from mt5_agent.ai.planner import (
    SYSTEM_PROMPT,
    LLMPlanner,
    Planner,
    build_user_prompt,
    hold_proposal,
    validate_proposal,
)
from mt5_agent.ai.provider import LLMProvider
from mt5_agent.domain.market import Candle, MarketSnapshot, Timeframe
from mt5_agent.domain.planning import PlannerInput, TradeAction
from mt5_agent.domain.strategy import Direction, Setup, StrategySignal


class FakeProvider(LLMProvider):
    """Deterministic provider double returning a canned structured payload."""

    name = "fake"

    def __init__(self, payload: Any, model: str = "fake-model") -> None:
        self._payload = payload
        self._model = model
        self.requests: list[LLMRequest] = []

    @property
    def model(self) -> str:
        return self._model

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if isinstance(self._payload, Exception):
            raise self._payload
        text = json.dumps(self._payload) if not isinstance(self._payload, str) else self._payload
        return LLMResponse(
            text,
            "fake",
            self._model,
            1.0,
            LLMUsage(1, 1, 2),
            structured=self._payload if not isinstance(self._payload, str) else None,
        )


def _input(direction: Direction = Direction.LONG) -> PlannerInput:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    candle = Candle("EURUSD", Timeframe.M1, now, 1.0, 1.2, 0.9, 1.15)
    snap = MarketSnapshot("EURUSD", Timeframe.M1, now, candles=(candle,))
    setup = Setup("d:breakout:long", "StructureBreakout", Direction.LONG, 0.6)
    signal = StrategySignal(
        "donchian_breakout",
        "EURUSD",
        Timeframe.M1,
        direction,
        0.6,
        (setup,),
        {"prior_high": 1.1},
        "break",
        now,
    )
    return PlannerInput("EURUSD", Timeframe.M1, snap, signal)


_BUY = {
    "action": "BUY",
    "entry": 1.15,
    "stop_loss": 1.14,
    "take_profit": 1.17,
    "risk_pct": 0.5,
    "volume": None,
    "confidence": 0.7,
    "rationale": "breakout",
}


def test_valid_buy_proposal() -> None:
    planner = LLMPlanner(FakeProvider(dict(_BUY)))
    proposal = planner.plan(_input())
    assert proposal.action == TradeAction.BUY
    assert proposal.entry == pytest.approx(1.15)
    assert proposal.setup_id == "d:breakout:long"
    assert proposal.strategy == "donchian_breakout"
    assert proposal.provider == "fake"
    assert planner.provider.name == "fake"


def test_directional_action_requires_matching_signal() -> None:
    proposal = LLMPlanner(FakeProvider(dict(_BUY))).plan(_input(Direction.FLAT))
    assert proposal.action == TradeAction.HOLD
    assert "degraded" in proposal.rationale.lower()


def test_opposite_directional_action_is_rejected() -> None:
    proposal = LLMPlanner(FakeProvider(dict(_BUY))).plan(_input(Direction.SHORT))
    assert proposal.action == TradeAction.HOLD


def test_valid_sell_proposal() -> None:
    payload = {
        "action": "SELL",
        "entry": 1.15,
        "stop_loss": 1.16,
        "take_profit": 1.13,
        "risk_pct": 0.25,
        "confidence": 0.6,
        "rationale": "breakdown",
    }
    proposal = LLMPlanner(FakeProvider(payload)).plan(_input(Direction.SHORT))
    assert proposal.action == TradeAction.SELL


def test_inconsistent_prices_fall_back_to_hold() -> None:
    bad = dict(_BUY, stop_loss=1.20)  # SL above entry for BUY
    proposal = LLMPlanner(FakeProvider(bad)).plan(_input())
    assert proposal.action == TradeAction.HOLD
    assert "degraded" in proposal.rationale.lower()


def test_malformed_output_falls_back_to_hold() -> None:
    proposal = LLMPlanner(FakeProvider("not json{{")).plan(_input())
    assert proposal.action == TradeAction.HOLD


def test_provider_error_falls_back_to_hold() -> None:
    planner = LLMPlanner(FakeProvider(LLMProviderError("down", provider="fake")))
    proposal = planner.plan(_input())
    assert proposal.action == TradeAction.HOLD
    assert proposal.confidence == 0.0


def test_validate_rejects() -> None:
    planner_input = _input()
    with pytest.raises(ValueError):
        validate_proposal({"action": "YOLO", "confidence": 0.5, "rationale": "x"}, planner_input)
    with pytest.raises(ValueError):
        validate_proposal(
            {"action": "BUY", "confidence": 0.5, "rationale": "x"}, planner_input
        )  # missing entry/SL/TP
    hold = validate_proposal({"action": "HOLD", "confidence": 0.0, "rationale": ""}, planner_input)
    assert hold.action == TradeAction.HOLD


def test_prompt_contains_context_and_contract() -> None:
    prompt = build_user_prompt(_input())
    data = json.loads(prompt)
    assert data["symbol"] == "EURUSD"
    assert data["strategy_signal"]["direction"] == "LONG"
    assert "prior_high" in data["strategy_signal"]["facts"]
    assert "BUY" in SYSTEM_PROMPT and "HOLD" in SYSTEM_PROMPT


def test_hold_helper_and_abc() -> None:
    assert hold_proposal(_input(), "wait").action == TradeAction.HOLD
    with pytest.raises(TypeError):
        Planner()  # type: ignore[abstract]


def test_planner_never_executes() -> None:
    import inspect

    from mt5_agent.ai import planner as planner_module

    source = inspect.getsource(planner_module)
    for forbidden in ("order_send", "order_check", "positions_get", "MetaTrader5"):
        assert forbidden not in source
