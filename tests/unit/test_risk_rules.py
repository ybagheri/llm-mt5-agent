"""Risk rule tests: every rule's pass/fail boundary (deterministic)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.planning import TradeAction, TradeProposal
from mt5_agent.domain.trading import AccountState, Position, PositionSide
from mt5_agent.risk.config import RiskConfig, TradingSession
from mt5_agent.risk.context import DecisionRecord, RiskContext
from mt5_agent.risk.engine import RiskEngine
from mt5_agent.risk.result import ValidationResult, ViolationCode


def _account(**kwargs: object) -> AccountState:
    base: dict[str, object] = {
        "account": AccountInfo(
            1, "S", "USD", 10000.0, 10000.0, 100.0, 9900.0, 0.0, trade_allowed=True
        ),
    }
    base.update(kwargs)
    return AccountState(**base)  # type: ignore[arg-type]


def _buy(**kwargs: object) -> TradeProposal:
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
        "volume": 0.1,
    }
    base.update(kwargs)
    return TradeProposal(**base)  # type: ignore[arg-type]


def _pos(
    symbol: str = "EURUSD", side: PositionSide = PositionSide.BUY, volume: float = 0.1
) -> Position:
    return Position(1, symbol, side, volume, 1.1, 1.2, time=datetime(2026, 1, 1, tzinfo=UTC))


def _ctx(**kwargs: object) -> RiskContext:
    base: dict[str, object] = {
        "account": _account(),
        "server_time": datetime(2026, 1, 6, 12, tzinfo=UTC),
        "day_pnl": 0.0,
    }
    base.update(kwargs)
    return RiskContext(**base)  # type: ignore[arg-type]


def test_hold_auto_approves() -> None:
    hold = TradeProposal(TradeAction.HOLD, "EURUSD", 0.0, "wait", "s")
    result = RiskEngine(RiskConfig()).validate(hold, _ctx())
    assert result.approved is True


def test_max_risk() -> None:
    engine = RiskEngine(RiskConfig(max_risk_pct_per_trade=1.0))
    assert engine.validate(_buy(risk_pct=0.5), _ctx()).approved is True
    result = engine.validate(_buy(risk_pct=2.0), _ctx())
    assert result.codes == (ViolationCode.MAX_RISK_EXCEEDED,)


def test_daily_loss() -> None:
    engine = RiskEngine(RiskConfig(max_daily_loss_pct=3.0))
    assert engine.validate(_buy(), _ctx(day_pnl=-100.0)).approved is True
    result = engine.validate(_buy(), _ctx(day_pnl=-300.0))
    assert ViolationCode.MAX_DAILY_LOSS_EXCEEDED in result.codes
    assert engine.validate(_buy(), _ctx(day_pnl=None)).codes == (
        ViolationCode.MAX_DAILY_LOSS_EXCEEDED,
    )


def test_max_positions() -> None:
    engine = RiskEngine(RiskConfig(max_open_positions=1))
    assert engine.validate(_buy(), _ctx(positions=(_pos(),))).approved is False
    assert engine.validate(_buy(), _ctx()).approved is True


def test_max_exposure() -> None:
    engine = RiskEngine(RiskConfig(max_exposure_volume=0.15))
    result = engine.validate(_buy(volume=0.1), _ctx(positions=(_pos(volume=0.1),)))
    assert ViolationCode.MAX_EXPOSURE_EXCEEDED in result.codes


def test_symbol_allowlist() -> None:
    engine = RiskEngine(RiskConfig(allowed_symbols=("EURUSD",)))
    assert engine.validate(_buy(), _ctx()).approved is True
    result = engine.validate(_buy(symbol="XAUUSD"), _ctx())
    assert result.codes == (ViolationCode.SYMBOL_NOT_ALLOWED,)
    assert RiskEngine(RiskConfig()).validate(_buy(symbol="XAUUSD"), _ctx()).approved is True


def test_session() -> None:
    engine = RiskEngine(RiskConfig(allowed_sessions=(TradingSession(8, 18),)))
    assert engine.validate(_buy(), _ctx()).approved is True
    night = _ctx(server_time=datetime(2026, 1, 6, 2, tzinfo=UTC))
    assert engine.validate(_buy(), night).codes == (ViolationCode.SESSION_CLOSED,)
    overnight = RiskEngine(RiskConfig(allowed_sessions=(TradingSession(20, 6),)))
    assert overnight.validate(_buy(), night).approved is True


def test_spread() -> None:
    engine = RiskEngine(RiskConfig(max_spread_points=20.0))
    assert engine.validate(_buy(), _ctx(spreads_points={"EURUSD": 10.0})).approved is True
    result = engine.validate(_buy(), _ctx(spreads_points={"EURUSD": 30.0}))
    assert result.codes == (ViolationCode.SPREAD_TOO_HIGH,)
    assert engine.validate(_buy(), _ctx()).codes == (ViolationCode.SPREAD_TOO_HIGH,)


def test_mandatory_sl_tp() -> None:
    assert RiskEngine(RiskConfig()).validate(_buy(stop_loss=None), _ctx()).codes == (
        ViolationCode.STOP_LOSS_REQUIRED,
    )
    assert RiskEngine(RiskConfig()).validate(_buy(take_profit=None), _ctx()).codes == (
        ViolationCode.TAKE_PROFIT_REQUIRED,
    )
    relaxed = RiskEngine(RiskConfig(require_stop_loss=False, require_take_profit=False))
    assert relaxed.validate(_buy(stop_loss=None, take_profit=None), _ctx()).approved is True


def test_min_stop_distance() -> None:
    engine = RiskEngine(RiskConfig(min_stop_points=100.0))
    ctx = _ctx(symbol_points={"EURUSD": 0.00001})
    assert engine.validate(_buy(), ctx).approved is True  # 1000pt
    result = engine.validate(_buy(stop_loss=1.09995), ctx)  # 5pt
    assert result.codes == (ViolationCode.STOP_TOO_CLOSE,)


def test_duplicate_open_position() -> None:
    result = RiskEngine(RiskConfig()).validate(_buy(), _ctx(positions=(_pos(),)))
    assert result.codes == (ViolationCode.DUPLICATE_TRADE,)
    sell = _buy(action=TradeAction.SELL, entry=1.1, stop_loss=1.11, take_profit=1.08)
    assert RiskEngine(RiskConfig()).validate(sell, _ctx(positions=(_pos(),))).approved is True


def test_duplicate_recent_approval() -> None:
    now = datetime(2026, 1, 6, 12, tzinfo=UTC)
    record = DecisionRecord("EURUSD", "BUY", True, now)
    ctx = _ctx(recent_decisions=(record,))
    result = RiskEngine(RiskConfig(duplicate_window_s=600.0)).validate(_buy(), ctx)
    assert ViolationCode.DUPLICATE_TRADE in result.codes


def test_cooldown() -> None:
    now = datetime(2026, 1, 6, 12, tzinfo=UTC)
    record = DecisionRecord("EURUSD", "HOLD", False, now)
    ctx = _ctx(server_time=now, recent_decisions=(record,))
    result = RiskEngine(RiskConfig(cooldown_s=60.0)).validate(_buy(), ctx)
    assert result.codes == (ViolationCode.COOLDOWN_ACTIVE,)
    old = DecisionRecord("EURUSD", "HOLD", False, datetime(2026, 1, 6, 11, tzinfo=UTC))
    assert (
        RiskEngine(RiskConfig(cooldown_s=60.0))
        .validate(_buy(), _ctx(server_time=now, recent_decisions=(old,)))
        .approved
        is True
    )


def test_account_safety() -> None:
    bad = _account(account=AccountInfo(1, "S", "USD", 1000.0, 1000.0, 0, 0, 0, trade_allowed=False))
    assert RiskEngine(RiskConfig()).validate(_buy(), _ctx(account=bad)).codes == (
        ViolationCode.ACCOUNT_UNSAFE,
    )
    low = _account(
        account=AccountInfo(1, "S", "USD", 1000.0, 50.0, 100.0, 0, 0, trade_allowed=True)
    )
    result = RiskEngine(RiskConfig(min_margin_level_pct=100.0)).validate(_buy(), _ctx(account=low))
    assert result.codes == (ViolationCode.ACCOUNT_UNSAFE,)


def test_multiple_violations_aggregated() -> None:
    engine = RiskEngine(RiskConfig(max_risk_pct_per_trade=0.1, allowed_symbols=("XAUUSD",)))
    result = engine.validate(_buy(risk_pct=5.0), _ctx())
    assert set(result.codes) == {ViolationCode.MAX_RISK_EXCEEDED, ViolationCode.SYMBOL_NOT_ALLOWED}


def test_result_invariants() -> None:
    with pytest.raises(ValueError):
        ValidationResult(True, (_ctx_viol(),))
    with pytest.raises(ValueError):
        ValidationResult(False, ())


def _ctx_viol():  # type: ignore[no-untyped-def]
    from mt5_agent.risk.result import Violation

    return Violation(ViolationCode.COOLDOWN_ACTIVE, "x")
