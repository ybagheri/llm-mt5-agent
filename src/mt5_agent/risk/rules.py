"""Deterministic risk rules: one concern per rule, explicit codes only."""

from __future__ import annotations

from abc import ABC, abstractmethod

from mt5_agent.domain.planning import TradeAction, TradeProposal
from mt5_agent.domain.trading import PositionSide
from mt5_agent.risk.config import RiskConfig
from mt5_agent.risk.context import RiskContext
from mt5_agent.risk.result import Violation, ViolationCode


class RiskRule(ABC):
    """Single deterministic check. Returns a violation or None (pass)."""

    code: ViolationCode
    name: str = "rule"

    @abstractmethod
    def check(
        self, proposal: TradeProposal, context: RiskContext, config: RiskConfig
    ) -> Violation | None: ...

    def _fail(self, message: str) -> Violation:
        return Violation(self.code, message, self.name)


def _side_of(proposal: TradeProposal) -> PositionSide | None:
    if proposal.action == TradeAction.BUY:
        return PositionSide.BUY
    if proposal.action == TradeAction.SELL:
        return PositionSide.SELL
    return None


class MaxRiskRule(RiskRule):
    code = ViolationCode.MAX_RISK_EXCEEDED
    name = "max_risk"

    def check(
        self, proposal: TradeProposal, context: RiskContext, config: RiskConfig
    ) -> Violation | None:
        if proposal.risk_pct > config.max_risk_pct_per_trade:
            return self._fail(
                f"risk {proposal.risk_pct}% exceeds max {config.max_risk_pct_per_trade}%"
            )
        return None


class DailyLossRule(RiskRule):
    code = ViolationCode.MAX_DAILY_LOSS_EXCEEDED
    name = "daily_loss"

    def check(
        self, proposal: TradeProposal, context: RiskContext, config: RiskConfig
    ) -> Violation | None:
        if context.day_pnl is None:
            return None  # unknown P&L: cannot evaluate (abstain, documented)
        limit = context.account.balance * config.max_daily_loss_pct / 100.0
        if context.day_pnl <= -limit:
            return self._fail(f"day P&L {context.day_pnl} breached daily loss limit {limit}")
        return None


class MaxPositionsRule(RiskRule):
    code = ViolationCode.MAX_POSITIONS_EXCEEDED
    name = "max_positions"

    def check(
        self, proposal: TradeProposal, context: RiskContext, config: RiskConfig
    ) -> Violation | None:
        if len(context.positions) >= config.max_open_positions:
            return self._fail(
                f"{len(context.positions)} open positions >= max {config.max_open_positions}"
            )
        return None


class MaxExposureRule(RiskRule):
    code = ViolationCode.MAX_EXPOSURE_EXCEEDED
    name = "max_exposure"

    def check(
        self, proposal: TradeProposal, context: RiskContext, config: RiskConfig
    ) -> Violation | None:
        current = sum(p.volume for p in context.positions)
        added = proposal.volume or 0.0
        if current + added > config.max_exposure_volume:
            return self._fail(
                f"exposure {current + added} exceeds max {config.max_exposure_volume}"
            )
        return None


class SymbolAllowlistRule(RiskRule):
    code = ViolationCode.SYMBOL_NOT_ALLOWED
    name = "symbol_allowlist"

    def check(
        self, proposal: TradeProposal, context: RiskContext, config: RiskConfig
    ) -> Violation | None:
        if config.allowed_symbols is None:
            return None
        if proposal.symbol not in config.allowed_symbols:
            return self._fail(f"symbol {proposal.symbol!r} not in allowlist")
        return None


class SessionRule(RiskRule):
    code = ViolationCode.SESSION_CLOSED
    name = "session"

    def check(
        self, proposal: TradeProposal, context: RiskContext, config: RiskConfig
    ) -> Violation | None:
        hour = context.server_time.hour
        if any(session.contains(hour) for session in config.allowed_sessions):
            return None
        return self._fail(f"hour {hour} outside allowed sessions")


class SpreadRule(RiskRule):
    code = ViolationCode.SPREAD_TOO_HIGH
    name = "spread"

    def check(
        self, proposal: TradeProposal, context: RiskContext, config: RiskConfig
    ) -> Violation | None:
        if config.max_spread_points is None:
            return None
        spread = context.spreads_points.get(proposal.symbol)
        if spread is None:
            return None  # unknown spread: abstain (documented)
        if spread > config.max_spread_points:
            return self._fail(f"spread {spread}pt exceeds max {config.max_spread_points}pt")
        return None


class StopLossRequiredRule(RiskRule):
    code = ViolationCode.STOP_LOSS_REQUIRED
    name = "stop_loss_required"

    def check(
        self, proposal: TradeProposal, context: RiskContext, config: RiskConfig
    ) -> Violation | None:
        if config.require_stop_loss and proposal.stop_loss is None:
            return self._fail("stop loss is mandatory")
        return None


class TakeProfitRequiredRule(RiskRule):
    code = ViolationCode.TAKE_PROFIT_REQUIRED
    name = "take_profit_required"

    def check(
        self, proposal: TradeProposal, context: RiskContext, config: RiskConfig
    ) -> Violation | None:
        if config.require_take_profit and proposal.take_profit is None:
            return self._fail("take profit is mandatory")
        return None


class MinStopDistanceRule(RiskRule):
    code = ViolationCode.STOP_TOO_CLOSE
    name = "min_stop_distance"

    def check(
        self, proposal: TradeProposal, context: RiskContext, config: RiskConfig
    ) -> Violation | None:
        if config.min_stop_points <= 0:
            return None
        if proposal.entry is None or proposal.stop_loss is None:
            return None
        point = context.symbol_points.get(proposal.symbol) or 0.0
        if point <= 0:
            return None  # unknown point size: abstain (documented)
        distance_points = abs(proposal.entry - proposal.stop_loss) / point
        if distance_points < config.min_stop_points:
            return self._fail(
                f"stop distance {distance_points:.1f}pt below min {config.min_stop_points}pt"
            )
        return None


class DuplicateTradeRule(RiskRule):
    code = ViolationCode.DUPLICATE_TRADE
    name = "duplicate"

    def check(
        self, proposal: TradeProposal, context: RiskContext, config: RiskConfig
    ) -> Violation | None:
        side = _side_of(proposal)
        if side is None:
            return None
        for position in context.positions:
            if position.symbol == proposal.symbol and position.side == side:
                return self._fail(f"open {side.name} position on {proposal.symbol} already exists")
        if config.duplicate_window_s <= 0:
            return None
        now = context.server_time
        for record in context.recent_decisions:
            if not record.approved or record.action == TradeAction.HOLD.value:
                continue
            if record.symbol != proposal.symbol or record.action != proposal.action.value:
                continue
            age = (now - record.at).total_seconds()
            if 0 <= age <= config.duplicate_window_s:
                return self._fail(
                    f"{proposal.action.value} on {proposal.symbol} approved {age:.0f}s ago"
                )
        return None


class CooldownRule(RiskRule):
    code = ViolationCode.COOLDOWN_ACTIVE
    name = "cooldown"

    def check(
        self, proposal: TradeProposal, context: RiskContext, config: RiskConfig
    ) -> Violation | None:
        if config.cooldown_s <= 0 or not context.recent_decisions:
            return None
        latest: float | None = None
        for record in context.recent_decisions:
            if record.symbol != proposal.symbol:
                continue
            age = (context.server_time - record.at).total_seconds()
            if age >= 0 and (latest is None or age < latest):
                latest = age
        if latest is not None and latest < config.cooldown_s:
            return self._fail(f"cooldown: last decision on {proposal.symbol} {latest:.0f}s ago")
        return None


class AccountSafetyRule(RiskRule):
    code = ViolationCode.ACCOUNT_UNSAFE
    name = "account_safety"

    def check(
        self, proposal: TradeProposal, context: RiskContext, config: RiskConfig
    ) -> Violation | None:
        account = context.account.account
        if not account.trade_allowed:
            return self._fail("account trade is disabled")
        if account.equity <= 0:
            return self._fail("account equity is not positive")
        level = context.account.margin_level
        if level is not None and level < config.min_margin_level_pct:
            return self._fail(f"margin level {level:.0f}% below min {config.min_margin_level_pct}%")
        return None


DEFAULT_RULES: tuple[RiskRule, ...] = (
    AccountSafetyRule(),
    SymbolAllowlistRule(),
    SessionRule(),
    MaxRiskRule(),
    DailyLossRule(),
    MaxPositionsRule(),
    MaxExposureRule(),
    SpreadRule(),
    StopLossRequiredRule(),
    TakeProfitRequiredRule(),
    MinStopDistanceRule(),
    DuplicateTradeRule(),
    CooldownRule(),
)


__all__ = ["DEFAULT_RULES", "RiskRule"]
