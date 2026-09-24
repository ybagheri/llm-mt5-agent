"""Supervisor tests: check purity, review ledger, duplicate/cooldown behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.planning import TradeAction, TradeProposal
from mt5_agent.domain.trading import AccountState
from mt5_agent.risk.config import RiskConfig
from mt5_agent.risk.context import RiskContext
from mt5_agent.risk.supervisor import Supervisor


def _proposal(**kwargs: object) -> TradeProposal:
    base: dict[str, object] = {
        "action": TradeAction.BUY,
        "symbol": "EURUSD",
        "confidence": 0.6,
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


def _context(now: datetime | None = None) -> RiskContext:
    account = AccountState(
        AccountInfo(1, "S", "USD", 10000.0, 10000.0, 100.0, 9900.0, 0.0, trade_allowed=True)
    )
    return RiskContext(
        account=account,
        server_time=now or datetime(2026, 1, 6, 12, tzinfo=UTC),
        day_pnl=0.0,
    )


def test_check_is_pure_and_hold_skipped() -> None:
    supervisor = Supervisor(config=RiskConfig())
    hold = TradeProposal(TradeAction.HOLD, "EURUSD", 0.0, "wait", "s")
    assert supervisor.check(hold, _context()).approved is True
    assert supervisor.check(_proposal(), _context()).approved is True
    assert supervisor.ledger == ()  # check() records nothing


def test_review_records_and_blocks_duplicates() -> None:
    now = datetime(2026, 1, 6, 12, tzinfo=UTC)
    supervisor = Supervisor(config=RiskConfig(duplicate_window_s=600.0, cooldown_s=0.0))
    first = supervisor.review(_proposal(), _context(now), now=now)
    assert first.approved is True
    assert len(supervisor.ledger) == 1
    second = supervisor.review(_proposal(), _context(now), now=now)
    assert second.approved is False
    assert "MAX_RISK_EXCEEDED" not in second.codes
    assert any(c in ("DUPLICATE_TRADE", "COOLDOWN_ACTIVE") for c in second.codes)


def test_review_rejection_also_recorded() -> None:
    now = datetime(2026, 1, 6, 12, tzinfo=UTC)
    supervisor = Supervisor(config=RiskConfig(cooldown_s=60.0, duplicate_window_s=0.0))
    bad = _proposal(risk_pct=50.0)
    decision = supervisor.review(bad, _context(now), now=now)
    assert decision.approved is False
    assert decision.codes == ("MAX_RISK_EXCEEDED",)
    # Rejection starts cooldown for the next proposal.
    follow = supervisor.review(
        _proposal(), _context(now + timedelta(seconds=10)), now=now + timedelta(seconds=10)
    )
    assert follow.approved is False
    assert follow.codes == ("COOLDOWN_ACTIVE",)


def test_hold_not_recorded() -> None:
    supervisor = Supervisor(config=RiskConfig())
    hold = TradeProposal(TradeAction.HOLD, "EURUSD", 0.0, "wait", "s")
    supervisor.review(hold, _context())
    assert supervisor.ledger == ()


def test_decision_carries_audit() -> None:
    supervisor = Supervisor(config=RiskConfig())
    decision = supervisor.review(_proposal(), _context())
    assert decision.proposal.symbol == "EURUSD"
    assert decision.decided_at.tzinfo is not None
