"""Planner: structured context in, `TradeProposal` out. Never executes orders.

`LLMPlanner` asks an `LLMProvider` for a JSON proposal, then validates it
strictly against the input (symbol match, price sanity, direction consistency).
Any LLM failure or malformed output degrades to a `HOLD` proposal — the safe
default the Supervisor (Phase 07) treats as a no-op.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from mt5_agent.ai.errors import LLMError
from mt5_agent.ai.models import LLMMessage, LLMRequest
from mt5_agent.ai.provider import LLMProvider
from mt5_agent.domain.planning import PlannerInput, TradeAction, TradeProposal

SYSTEM_PROMPT = """You are a cautious trading planner for a supervised demo-first \
MetaTrader 5 agent. You NEVER execute trades; you output exactly one JSON object \
with this schema (no markdown, no commentary):
{"action": "BUY"|"SELL"|"HOLD", "entry": number|null, "stop_loss": number|null, \
"take_profit": number|null, "risk_pct": number, "volume": number|null, \
"confidence": number, "rationale": string}
Rules: HOLD unless the strategy signal is directional AND the setup justifies \
action; BUY requires stop_loss < entry < take_profit; SELL requires \
take_profit < entry < stop_loss; risk_pct in 0..100; confidence in 0..1; \
rationale must reference the strategy facts. The deterministic Supervisor will \
reject anything unsafe, so prefer HOLD when uncertain."""


class Planner(ABC):
    """Abstract planner: structured input -> validated `TradeProposal`."""

    @abstractmethod
    def plan(self, planner_input: PlannerInput) -> TradeProposal:
        """Produce exactly one proposal. Must never execute orders or raise blindly."""
        ...


class LLMPlanner(Planner):
    """LLM-backed planner with strict output validation and HOLD fallback."""

    def __init__(self, provider: LLMProvider, *, strategy_name: str = "llm_planner") -> None:
        self._provider = provider
        self._strategy_name = strategy_name

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    def plan(self, planner_input: PlannerInput) -> TradeProposal:
        request = LLMRequest(
            (
                LLMMessage("system", SYSTEM_PROMPT),
                LLMMessage("user", build_user_prompt(planner_input)),
            ),
            response_format="json",
            temperature=0.2,
        )
        try:
            response = self._provider.generate(request)
            data = response.structured
            if not isinstance(data, dict):
                raise ValueError("LLM did not return a JSON object")
            return validate_proposal(
                data,
                planner_input,
                provider=response.provider,
                model=response.model,
                latency_ms=response.latency_ms,
            )
        except Exception as exc:  # fail safely: HOLD, never raise into trading path
            reason = f"Planner degraded to HOLD ({type(exc).__name__}: {exc})"
            if isinstance(exc, LLMError):
                reason = f"Planner degraded to HOLD ({exc})"
            return TradeProposal(
                action=TradeAction.HOLD,
                symbol=planner_input.symbol,
                confidence=0.0,
                rationale=reason,
                strategy=self._strategy_name,
                provider=getattr(self._provider, "name", ""),
                model=getattr(self._provider, "model", ""),
            )


def build_user_prompt(planner_input: PlannerInput) -> str:
    """Serialize planner context deterministically (stable key order)."""
    snapshot = planner_input.snapshot
    candles = [
        {"t": c.time.isoformat(), "o": c.open, "h": c.high, "l": c.low, "c": c.close}
        for c in snapshot.candles[-20:]
    ]
    tick = (
        {"bid": snapshot.tick.bid, "ask": snapshot.tick.ask, "time": snapshot.tick.time.isoformat()}
        if snapshot.tick
        else None
    )
    account = (
        {
            "balance": planner_input.account.balance,
            "equity": planner_input.account.equity,
            "margin": planner_input.account.margin,
            "free_margin": planner_input.account.free_margin,
            "open_positions": planner_input.account.open_positions,
            "exposure_volume": planner_input.account.exposure_volume,
            "floating_profit": planner_input.account.floating_profit,
        }
        if planner_input.account
        else None
    )
    payload = {
        "symbol": planner_input.symbol,
        "timeframe": planner_input.timeframe.value,
        "strategy_signal": {
            "strategy": planner_input.signal.strategy,
            "direction": planner_input.signal.direction.value,
            "confidence": planner_input.signal.confidence,
            "setups": [s.identifier for s in planner_input.signal.setups],
            "facts": planner_input.signal.facts,
            "rationale": planner_input.signal.rationale,
        },
        "market": {"candles": candles, "tick": tick},
        "account": account,
        "open_positions": [
            {"ticket": p.ticket, "side": p.side.name, "volume": p.volume, "profit": p.profit}
            for p in planner_input.open_positions
        ],
        "memory": [{"kind": m.kind, "text": m.text} for m in planner_input.memory],
    }
    return json.dumps(payload, default=str)


def validate_proposal(
    data: dict[str, Any],
    planner_input: PlannerInput,
    *,
    provider: str = "",
    model: str = "",
    latency_ms: float = 0.0,
) -> TradeProposal:
    """Strictly validate raw LLM JSON into a `TradeProposal` (raises on violation)."""
    try:
        action = TradeAction(str(data.get("action", "")).upper())
    except ValueError as exc:
        raise ValueError(f"invalid action: {data.get('action')!r}") from exc
    entry = _opt_float(data.get("entry"), "entry")
    stop_loss = _opt_float(data.get("stop_loss"), "stop_loss")
    take_profit = _opt_float(data.get("take_profit"), "take_profit")
    risk_pct = _req_float(data.get("risk_pct", 0.0), "risk_pct")
    volume = _opt_float(data.get("volume"), "volume")
    confidence = _req_float(data.get("confidence", 0.0), "confidence")
    rationale = str(data.get("rationale", "") or "")
    if action == TradeAction.HOLD:
        return TradeProposal(
            action=action,
            symbol=planner_input.symbol,
            confidence=_clamp01(confidence),
            rationale=rationale or "LLM chose HOLD.",
            strategy=planner_input.signal.strategy,
            setup_id=_first_setup(planner_input),
            risk_pct=_check_risk(risk_pct),
            provider=provider,
            model=model,
            latency_ms=latency_ms,
        )
    signal_direction = planner_input.signal.direction
    expected_direction = "LONG" if action == TradeAction.BUY else "SHORT"
    if signal_direction.value != expected_direction:
        raise ValueError(
            f"{action.value} requires deterministic signal direction {expected_direction}; "
            f"received {signal_direction.value}"
        )
    if entry is None:
        raise ValueError("directional proposals require entry")
    if stop_loss is None or take_profit is None:
        raise ValueError("directional proposals require stop_loss and take_profit")
    if action == TradeAction.BUY and not (stop_loss < entry < take_profit):
        raise ValueError("BUY requires stop_loss < entry < take_profit")
    if action == TradeAction.SELL and not (take_profit < entry < stop_loss):
        raise ValueError("SELL requires take_profit < entry < stop_loss")
    if not rationale.strip():
        raise ValueError("rationale must be non-empty")
    return TradeProposal(
        action=action,
        symbol=planner_input.symbol,
        confidence=_clamp01(confidence),
        rationale=rationale,
        strategy=planner_input.signal.strategy,
        setup_id=_first_setup(planner_input),
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_pct=_check_risk(risk_pct),
        volume=volume,
        provider=provider,
        model=model,
        latency_ms=latency_ms,
    )


def _first_setup(planner_input: PlannerInput) -> str:
    setups = planner_input.signal.setups
    return setups[0].identifier if setups else ""


def _opt_float(value: Any, name: str) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _req_float(value: Any, name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc


def _clamp01(value: float) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError("confidence must be 0..1")
    return value


def _check_risk(value: float) -> float:
    if not 0.0 <= value <= 100.0:
        raise ValueError("risk_pct must be 0..100")
    return value


def hold_proposal(planner_input: PlannerInput, rationale: str) -> TradeProposal:
    """Build an explicit HOLD proposal (used by orchestrators, never by LLM)."""
    return TradeProposal(
        action=TradeAction.HOLD,
        symbol=planner_input.symbol,
        confidence=0.0,
        rationale=rationale,
        strategy=planner_input.signal.strategy,
        created_at=datetime.now(UTC),
    )


__all__ = [
    "LLMPlanner",
    "Planner",
    "SYSTEM_PROMPT",
    "build_user_prompt",
    "hold_proposal",
    "validate_proposal",
]
