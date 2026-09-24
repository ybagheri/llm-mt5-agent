"""Dashboard state provider: assembles read-only sections (best-effort each)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from mt5_agent.ai.models import LLMResponse
from mt5_agent.application.account_service import AccountService
from mt5_agent.application.history_service import HistoryService
from mt5_agent.application.market_service import MarketService
from mt5_agent.application.order_service import OrderService
from mt5_agent.application.position_service import PositionService
from mt5_agent.application.strategy_service import StrategyService
from mt5_agent.dashboard.costs import estimate_cost_usd
from mt5_agent.dashboard.state import (
    AccountSection,
    AgentSection,
    DashboardState,
    LLMSection,
    MarketSection,
    MemorySection,
    RiskSection,
)
from mt5_agent.domain.market import Timeframe
from mt5_agent.memory.memories import StrategyMemory, TradeMemory, WorldMemory
from mt5_agent.risk.config import RiskConfig

logger = logging.getLogger(__name__)


class DashboardStateProvider:
    """Builds `DashboardState` from injected services (all reads, no writes)."""

    def __init__(
        self,
        *,
        market: MarketService,
        account: AccountService,
        positions: PositionService,
        orders: OrderService,
        strategies: StrategyService,
        risk_config: RiskConfig,
        history: HistoryService | None = None,
        trade_memory: TradeMemory | None = None,
        strategy_memory: StrategyMemory | None = None,
        world_memory: WorldMemory | None = None,
        llm_provider_name: str = "none",
        llm_model: str = "",
        version: str = "",
        trading_mode: str = "",
    ) -> None:
        self._market = market
        self._account = account
        self._positions = positions
        self._orders = orders
        self._strategies = strategies
        self._risk_config = risk_config
        self._history = history
        self._trade_memory = trade_memory
        self._strategy_memory = strategy_memory
        self._world_memory = world_memory
        self._llm_provider_name = llm_provider_name
        self._llm_model = llm_model
        self._version = version
        self._trading_mode = trading_mode
        self._last_llm: LLMResponse | None = None

    def record_llm(self, response: LLMResponse) -> None:
        """Remember the latest LLM call for the LLM section (display only)."""
        self._last_llm = response

    def build(self, symbol: str, timeframe: Timeframe) -> DashboardState:
        """Assemble state; core failure yields a state with `error` set."""
        try:
            snapshot = self._market.get_snapshot(symbol, timeframe, count=30)
            state = self._account.get_state()
        except Exception as exc:
            logger.warning("dashboard core read failed: %s", exc)
            return DashboardState(
                error=str(exc), version=self._version, trading_mode=self._trading_mode
            )
        return DashboardState(
            account=self._account_section(state),
            market=self._market_section(symbol, timeframe, snapshot),
            agent=self._agent_section(symbol, snapshot),
            risk=self._risk_section(state),
            memory=self._memory_section(),
            llm=self._llm_section(),
            version=self._version,
            trading_mode=self._trading_mode,
        )

    # -- sections (each best-effort) ---------------------------------------
    def _account_section(self, state: Any) -> AccountSection:
        return AccountSection(
            balance=state.balance,
            equity=state.equity,
            margin=state.margin,
            free_margin=state.free_margin,
            floating_profit=state.floating_profit,
            day_pnl=self._day_pnl(state),
            currency=state.account.currency,
            server=state.account.server,
        )

    def _day_pnl(self, state: Any) -> float | None:
        if self._history is None:
            return None
        try:
            now = datetime.now(UTC)
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            deals = self._history.deals(start, now)
            return float(self._history.realized_profit(deals) + state.floating_profit)
        except Exception as exc:
            logger.warning("day pnl unavailable: %s", exc)
            return None

    def _market_section(self, symbol: str, timeframe: Timeframe, snapshot: Any) -> MarketSection:
        tick = snapshot.tick
        spread_points: float | None = None
        try:
            info = self._market.get_symbol_info(symbol)
            if tick is not None and info.point > 0:
                spread_points = round((tick.ask - tick.bid) / info.point, 1)
        except Exception as exc:
            logger.warning("symbol info unavailable: %s", exc)
        now = datetime.now(UTC)
        return MarketSection(
            symbol=symbol,
            timeframe=timeframe.value,
            bid=tick.bid if tick else None,
            ask=tick.ask if tick else None,
            spread_points=spread_points,
            latest_close=snapshot.latest_close,
            session_open=any(s.contains(now.hour) for s in self._risk_config.allowed_sessions),
            server_time=now.isoformat(),
        )

    def _agent_section(self, symbol: str, snapshot: Any) -> AgentSection:
        try:
            from mt5_agent.domain.strategy import MarketContext, select_primary

            context = MarketContext(symbol, snapshot.timeframe, snapshot)
            signals = self._strategies.analyze(context)
            primary = select_primary(signals)
            return AgentSection(
                state="ready",
                strategy=primary.strategy,
                direction=primary.direction.value,
                confidence=primary.confidence,
                proposal_action="HOLD",
                proposal_summary=primary.rationale[:120],
            )
        except Exception as exc:
            logger.warning("agent section unavailable: %s", exc)
            return AgentSection(state="degraded", proposal_summary=str(exc))

    def _risk_section(self, state: Any) -> RiskSection:
        return RiskSection(
            max_risk_pct=self._risk_config.max_risk_pct_per_trade,
            exposure_volume=state.exposure_volume,
            max_exposure_volume=self._risk_config.max_exposure_volume,
            open_positions=state.open_positions,
            max_open_positions=self._risk_config.max_open_positions,
            day_pnl=self._day_pnl(state),
            max_daily_loss_pct=self._risk_config.max_daily_loss_pct,
        )

    def _memory_section(self) -> MemorySection:
        def rows(memory: Any, limit: int) -> tuple[dict[str, Any], ...]:
            if memory is None:
                return ()
            try:
                return tuple(
                    {"kind": r.kind.value, "symbol": r.symbol, "summary": r.summary}
                    for r in memory.recent(limit=limit)
                )
            except Exception as exc:
                logger.warning("memory read failed: %s", exc)
                return ()

        trades = rows(self._trade_memory, 10)
        return MemorySection(
            recent_decisions=tuple(r for r in trades if r["kind"] == "supervisor_decision"),
            recent_trades=tuple(r for r in trades if r["kind"] in ("execution", "outcome")),
            recent_events=rows(self._world_memory, 5) + rows(self._strategy_memory, 5),
        )

    def _llm_section(self) -> LLMSection:
        last = self._last_llm
        if last is None:
            return LLMSection(provider=self._llm_provider_name, model=self._llm_model)
        return LLMSection(
            provider=last.provider,
            model=last.model,
            latency_ms=round(last.latency_ms, 1),
            prompt_tokens=last.usage.prompt_tokens,
            completion_tokens=last.usage.completion_tokens,
            total_tokens=last.usage.total_tokens,
            estimated_cost_usd=estimate_cost_usd(
                last.model, last.usage.prompt_tokens, last.usage.completion_tokens
            ),
        )


__all__ = ["DashboardStateProvider"]
