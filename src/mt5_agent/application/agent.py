"""Agent orchestrator: OBSERVE -> ... -> MEMORY UPDATE as explicit stages.

Each stage is a small method producing a `StageOutcome`; `run_cycle()` chains
them in order with fail-safe degradation (a failed stage marks FAILED and the
cycle continues only where safe). `run()` loops `run_cycle()` until `stop()`
is called (graceful shutdown via `threading.Event`, signal wiring in scripts).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from mt5_agent.ai.planner import Planner, hold_proposal
from mt5_agent.application.account_service import AccountService
from mt5_agent.application.market_service import MarketService
from mt5_agent.application.order_service import OrderService
from mt5_agent.application.position_service import PositionService
from mt5_agent.application.strategy_service import StrategyService
from mt5_agent.application.watchdog import Watchdog
from mt5_agent.domain.agent import (
    AgentCycle,
    Stage,
    StageOutcome,
    StageStatus,
    new_cycle_id,
)
from mt5_agent.domain.market import MarketSnapshot, Timeframe
from mt5_agent.domain.planning import MemoryNote, PlannerInput, TradeAction
from mt5_agent.domain.strategy import MarketContext, select_primary
from mt5_agent.domain.trading import AccountState, Order, Position
from mt5_agent.execution.executor import TradeExecutor
from mt5_agent.logging_utils import audit
from mt5_agent.memory.memories import (
    ShortTermMemory,
    StrategyMemory,
    TradeMemory,
    WorldMemory,
)
from mt5_agent.risk.context import RiskContext
from mt5_agent.risk.supervisor import Supervisor

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Observation:
    """OBSERVE output: market + account state at one instant."""

    snapshot: MarketSnapshot
    account: AccountState
    positions: tuple[Position, ...]
    orders: tuple[Order, ...]
    observed_at: datetime


class Observer:
    """Gathers read-only state (no decisions, no writes except logs)."""

    def __init__(
        self,
        market: MarketService,
        account: AccountService,
        positions: PositionService,
        orders: OrderService,
    ) -> None:
        self._market = market
        self._account = account
        self._positions = positions
        self._orders = orders

    def observe(self, symbol: str, timeframe: Timeframe, count: int = 50) -> Observation:
        snapshot = self._market.get_snapshot(symbol, timeframe, count=count)
        return Observation(
            snapshot=snapshot,
            account=self._account.get_state(),
            positions=tuple(self._positions.open_positions()),
            orders=tuple(self._orders.pending_orders()),
            observed_at=datetime.now(UTC),
        )


class ContextBuilder:
    """Builds `MarketContext` + `PlannerInput` (memory notes included)."""

    def __init__(
        self,
        strategies: StrategyService,
        strategy_memory: StrategyMemory | None = None,
        trade_memory: TradeMemory | None = None,
        memory_notes_limit: int = 5,
    ) -> None:
        self._strategies = strategies
        self._strategy_memory = strategy_memory
        self._trade_memory = trade_memory
        self._memory_notes_limit = memory_notes_limit

    @property
    def strategies(self) -> StrategyService:
        return self._strategies

    def build_context(self, observation: Observation) -> MarketContext:
        return MarketContext(
            observation.snapshot.symbol,
            observation.snapshot.timeframe,
            observation.snapshot,
            observation.account,
        )

    def build_planner_input(
        self, observation: Observation, signal_index: int | None = None
    ) -> PlannerInput:
        """Build planner input. `None` (default) auto-selects the primary signal
        (first directional, else first); an explicit index pins one strategy
        (useful for debugging multi-strategy routing)."""
        context = self.build_context(observation)
        signals = self._strategies.analyze(context)
        if signal_index is None:
            signal = select_primary(signals)
        else:
            signal = signals[min(signal_index, len(signals) - 1)]
        return PlannerInput(
            observation.snapshot.symbol,
            observation.snapshot.timeframe,
            observation.snapshot,
            signal,
            observation.account,
            tuple(
                position
                for position in observation.positions
                if position.symbol == observation.snapshot.symbol
            ),
            self.memory_notes(observation.snapshot.symbol),
        )

    def memory_notes(self, symbol: str) -> tuple[MemoryNote, ...]:
        notes: list[MemoryNote] = []
        for memory, scope in ((self._strategy_memory, "strategy"), (self._trade_memory, "trade")):
            if memory is None:
                continue
            try:
                for record in memory.recent(limit=self._memory_notes_limit, symbol=symbol):
                    notes.append(MemoryNote(f"{scope}/{record.kind.value}", record.summary))
            except Exception as exc:  # memory must never break planning
                logger.warning("memory read failed: %s", exc)
        return tuple(notes[: self._memory_notes_limit * 2])


class TradingAgent:
    """Runs the 9-stage lifecycle. All collaborators injected (testable)."""

    def __init__(
        self,
        *,
        observer: Observer,
        context_builder: ContextBuilder,
        planner: Planner | None,
        supervisor: Supervisor,
        executor: TradeExecutor,
        short_term: ShortTermMemory | None = None,
        trade_memory: TradeMemory | None = None,
        strategy_memory: StrategyMemory | None = None,
        world_memory: WorldMemory | None = None,
        candle_count: int = 50,
        default_volume: float = 0.01,
        watchdog: Watchdog | None = None,
    ) -> None:
        self._observer = observer
        self._context_builder = context_builder
        self._planner = planner
        self._supervisor = supervisor
        self._executor = executor
        self._short_term = short_term
        self._trade_memory = trade_memory
        self._strategy_memory = strategy_memory
        self._world_memory = world_memory
        self._candle_count = candle_count
        self._default_volume = default_volume
        self._watchdog = watchdog
        self._stop = threading.Event()
        self._cycles = 0

    @property
    def cycles_completed(self) -> int:
        return self._cycles

    @property
    def watchdog(self) -> Watchdog | None:
        return self._watchdog

    def stop(self) -> None:
        """Request graceful shutdown (loop exits after the current cycle)."""
        self._stop.set()

    def run_cycle(self, symbol: str, timeframe: Timeframe) -> AgentCycle:
        """Execute one full lifecycle; never raises (failures become outcomes)."""
        if self._watchdog is not None and self._watchdog.should_halt():
            logger.warning(
                "agent cycle refused: watchdog halted new activity",
                extra={"extra_fields": {"symbol": symbol}},
            )
            started = datetime.now(UTC)
            return AgentCycle(
                new_cycle_id(),
                symbol,
                timeframe.value,
                (StageOutcome(Stage.OBSERVE, StageStatus.SKIPPED, "watchdog halt: no new cycles"),),
                started,
                datetime.now(UTC),
                "watchdog halt",
            )
        cycle_id = new_cycle_id()
        started = datetime.now(UTC)
        outcomes: list[StageOutcome] = []
        state: dict[str, Any] = {"cycle_id": cycle_id}
        error = ""
        try:
            self._observe(symbol, timeframe, outcomes, state)
            if _failed(outcomes):
                return self._finish_watchdog(cycle_id, symbol, timeframe, started, outcomes, error)
            self._strategy_memory_stage(outcomes, state)
            self._plan_stage(outcomes, state)
            self._supervise_stage(outcomes, state)
            self._execute_stage(outcomes, state)
            self._verify_stage(outcomes, state)
            self._memory_update_stage(outcomes, state)
        except Exception as exc:  # last-resort guard: cycle reports, never raises
            error = f"{type(exc).__name__}: {exc}"
            logger.exception("agent cycle failed")
        return self._finish_watchdog(cycle_id, symbol, timeframe, started, outcomes, error)

    def run(
        self,
        symbols: list[str],
        timeframe: Timeframe,
        *,
        interval_s: float = 60.0,
        max_cycles: int | None = None,
    ) -> list[AgentCycle]:
        """Loop cycles round-robin until `stop()` or `max_cycles` (graceful)."""
        cycles: list[AgentCycle] = []
        index = 0
        while not self._stop.is_set():
            if max_cycles is not None and len(cycles) >= max_cycles:
                break
            if self._watchdog is not None and self._watchdog.should_halt():
                logger.warning("agent loop halted by watchdog: no new cycles started")
                break
            symbol = symbols[index % len(symbols)]
            cycles.append(self.run_cycle(symbol, timeframe))
            self._cycles += 1
            index += 1
            if max_cycles is not None and len(cycles) >= max_cycles:
                break
            if interval_s > 0:
                self._stop.wait(interval_s)
        return cycles

    # -- stages ----------------------------------------------------------
    def _observe(
        self,
        symbol: str,
        timeframe: Timeframe,
        outcomes: list[StageOutcome],
        state: dict[str, Any],
    ) -> None:
        try:
            observation = self._observer.observe(symbol, timeframe, count=self._candle_count)
            state["observation"] = observation
            if self._watchdog is not None:
                self._watchdog.note_observation(observation.observed_at)
            outcomes.append(
                StageOutcome(
                    Stage.OBSERVE,
                    StageStatus.OK,
                    f"{symbol} close={observation.snapshot.latest_close}",
                    data={"candles": len(observation.snapshot.candles)},
                )
            )
            context = self._context_builder.build_context(observation)
            state["context"] = context
            outcomes.append(StageOutcome(Stage.CONTEXT, StageStatus.OK, "context built"))
        except Exception as exc:
            outcomes.append(StageOutcome(Stage.OBSERVE, StageStatus.FAILED, str(exc)))

    def _strategy_memory_stage(self, outcomes: list[StageOutcome], state: dict[str, Any]) -> None:
        try:
            context: MarketContext = state["context"]
            signals = self._context_builder.strategies.analyze(context)
            state["signals"] = signals
            # Primary = first directional signal (else the baseline). NullStrategy
            # stays registered first as the safe always-FLAT fallback; selection
            # (not order) decides what the Planner sees.
            primary = select_primary(signals)
            state["signal"] = primary
            if self._strategy_memory is not None:
                try:
                    self._strategy_memory.record_signal(primary)
                except Exception as exc:
                    logger.warning("signal memory write failed: %s", exc)
            # MEMORY stage: pull planner-input notes (read side of memory).
            notes = self._context_builder.memory_notes(context.symbol)
            state["memory_notes"] = notes
            outcomes.append(
                StageOutcome(
                    Stage.STRATEGY,
                    StageStatus.OK,
                    f"{primary.strategy}:{primary.direction.value}",
                    data={"signals": len(signals)},
                )
            )
            outcomes.append(StageOutcome(Stage.MEMORY, StageStatus.OK, f"{len(notes)} notes"))
        except Exception as exc:
            outcomes.append(StageOutcome(Stage.STRATEGY, StageStatus.FAILED, str(exc)))

    def _plan_stage(self, outcomes: list[StageOutcome], state: dict[str, Any]) -> None:
        try:
            observation: Observation = state["observation"]
            planner_input = self._context_builder.build_planner_input(observation)
            state["planner_input"] = planner_input
            if self._planner is None:
                proposal = hold_proposal(planner_input, "LLM not configured: HOLD")
            else:
                proposal = self._planner.plan(planner_input)
            state["proposal"] = proposal
            if self._trade_memory is not None:
                try:
                    self._trade_memory.record_proposal(proposal)
                except Exception as exc:
                    logger.warning("proposal memory write failed: %s", exc)
            outcomes.append(
                StageOutcome(
                    Stage.PLAN,
                    StageStatus.OK,
                    f"{proposal.action.value} conf={proposal.confidence:.2f}",
                )
            )
        except Exception as exc:
            outcomes.append(StageOutcome(Stage.PLAN, StageStatus.FAILED, str(exc)))

    def _supervise_stage(self, outcomes: list[StageOutcome], state: dict[str, Any]) -> None:
        try:
            observation: Observation = state["observation"]
            proposal = state["proposal"]
            if proposal.is_actionable and proposal.volume is None:
                proposal = replace(proposal, volume=self._default_volume)
                state["proposal"] = proposal
            tick = observation.snapshot.tick
            info = observation.snapshot.symbol_info
            spread_points: dict[str, float] = {}
            symbol_points: dict[str, float] = {}
            if tick is not None and info is not None and info.point > 0:
                spread_points[observation.snapshot.symbol] = tick.spread / info.point
                symbol_points[observation.snapshot.symbol] = info.point
            context = RiskContext(
                account=observation.account,
                positions=observation.positions,
                orders=observation.orders,
                spreads_points=spread_points,
                symbol_points=symbol_points,
                server_time=datetime.now(UTC),
                day_pnl=observation.account.day_realized_pnl,
            )
            decision = self._supervisor.review(proposal, context)
            state["decision"] = decision
            if self._trade_memory is not None:
                try:
                    self._trade_memory.record_decision(decision)
                except Exception as exc:
                    logger.warning("decision memory write failed: %s", exc)
            status = "approved" if decision.approved else f"rejected [{','.join(decision.codes)}]"
            outcomes.append(StageOutcome(Stage.SUPERVISE, StageStatus.OK, status))
        except Exception as exc:
            outcomes.append(StageOutcome(Stage.SUPERVISE, StageStatus.FAILED, str(exc)))

    def _execute_stage(self, outcomes: list[StageOutcome], state: dict[str, Any]) -> None:
        try:
            decision = state.get("decision")
            if decision is None or not decision.approved:
                outcomes.append(StageOutcome(Stage.EXECUTE, StageStatus.SKIPPED, "not approved"))
                return
            if decision.proposal.action == TradeAction.HOLD:
                outcomes.append(StageOutcome(Stage.EXECUTE, StageStatus.SKIPPED, "HOLD"))
                return
            record = self._executor.execute(decision, client_id=state.get("cycle_id"))
            state["record"] = record
            if self._trade_memory is not None:
                try:
                    self._trade_memory.record_execution(record)
                except Exception as exc:
                    logger.warning("execution memory write failed: %s", exc)
            outcomes.append(
                StageOutcome(
                    Stage.EXECUTE, StageStatus.OK, f"{record.status.value} ticket={record.ticket}"
                )
            )
        except Exception as exc:
            outcomes.append(StageOutcome(Stage.EXECUTE, StageStatus.FAILED, str(exc)))

    def _verify_stage(self, outcomes: list[StageOutcome], state: dict[str, Any]) -> None:
        try:
            record = state.get("record")
            if record is None:
                outcomes.append(StageOutcome(Stage.VERIFY, StageStatus.SKIPPED, "nothing executed"))
                return
            outcomes.append(
                StageOutcome(
                    Stage.VERIFY,
                    StageStatus.OK,
                    f"{record.status.value} slippage={record.slippage}",
                )
            )
        except Exception as exc:
            outcomes.append(StageOutcome(Stage.VERIFY, StageStatus.FAILED, str(exc)))

    def _memory_update_stage(self, outcomes: list[StageOutcome], state: dict[str, Any]) -> None:
        try:
            notes = 0
            if self._short_term is not None and "observation" in state:
                try:
                    self._short_term.record_observation(state["observation"].snapshot)
                    notes += 1
                except Exception as exc:
                    logger.warning("observation memory write failed: %s", exc)
            if self._trade_memory is not None and "record" in state:
                try:
                    record = state["record"]
                    self._trade_memory.record_outcome(
                        record.symbol, f"cycle {record.status.value}", status=record.status.value
                    )
                    notes += 1
                except Exception as exc:
                    logger.warning("outcome memory write failed: %s", exc)
            outcomes.append(StageOutcome(Stage.MEMORY_UPDATE, StageStatus.OK, f"{notes} writes"))
        except Exception as exc:
            outcomes.append(StageOutcome(Stage.MEMORY_UPDATE, StageStatus.FAILED, str(exc)))

    def _finish_watchdog(
        self,
        cycle_id: str,
        symbol: str,
        timeframe: Timeframe,
        started: datetime,
        outcomes: list[StageOutcome],
        error: str,
    ) -> AgentCycle:
        """Finish a cycle and report its outcome to the watchdog (if any)."""
        cycle = self._finish(cycle_id, symbol, timeframe, started, outcomes, error)
        if self._watchdog is not None:
            if cycle.ok:
                self._watchdog.note_success("cycle")
            else:
                self._watchdog.note_failure("cycle", cycle.error or "cycle degraded")
        return cycle

    def _finish(
        self,
        cycle_id: str,
        symbol: str,
        timeframe: Timeframe,
        started: datetime,
        outcomes: list[StageOutcome],
        error: str,
    ) -> AgentCycle:
        finished = datetime.now(UTC)
        ok = not error and not _failed(outcomes)
        logger.info(
            "agent cycle %s %s",
            cycle_id,
            "ok" if ok else "degraded",
            extra={"extra_fields": {"cycle": cycle_id, "symbol": symbol, "stages": len(outcomes)}},
        )
        audit(
            logger,
            "agent_cycle",
            cycle=cycle_id,
            symbol=symbol,
            ok=ok,
            stages=len(outcomes),
            error=error,
        )
        return AgentCycle(
            cycle_id, symbol, timeframe.value, tuple(outcomes), started, finished, error
        )


def _failed(outcomes: list[StageOutcome]) -> bool:
    return any(o.status == StageStatus.FAILED for o in outcomes)


__all__ = ["ContextBuilder", "Observation", "Observer", "TradingAgent"]
