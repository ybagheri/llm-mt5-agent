"""Agent orchestrator: OBSERVE -> ... -> MEMORY UPDATE as explicit stages.

Each stage is a small method producing a `StageOutcome`; `run_cycle()` chains
them in order with fail-safe degradation (a failed stage marks FAILED and the
cycle continues only where safe). `run()` loops `run_cycle()` until `stop()`
is called (graceful shutdown via `threading.Event`, signal wiring in scripts).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from mt5_agent.ai.planner import Planner, hold_proposal
from mt5_agent.application.account_service import AccountService
from mt5_agent.application.market_service import MarketService
from mt5_agent.application.order_service import OrderService
from mt5_agent.application.position_service import PositionService
from mt5_agent.application.strategy_service import StrategyService
from mt5_agent.domain.agent import (
    AgentCycle,
    Stage,
    StageOutcome,
    StageStatus,
    new_cycle_id,
)
from mt5_agent.domain.market import MarketSnapshot, Timeframe
from mt5_agent.domain.planning import MemoryNote, PlannerInput, TradeAction
from mt5_agent.domain.strategy import MarketContext
from mt5_agent.domain.trading import AccountState, Order, Position
from mt5_agent.execution.executor import MT5TradeExecutor
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
            positions=tuple(self._positions.open_positions(symbol)),
            orders=tuple(self._orders.pending_orders(symbol)),
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

    def build_planner_input(self, observation: Observation, signal_index: int = 0) -> PlannerInput:
        context = self.build_context(observation)
        signals = self._strategies.analyze(context)
        signal = signals[min(signal_index, len(signals) - 1)]
        return PlannerInput(
            observation.snapshot.symbol,
            observation.snapshot.timeframe,
            observation.snapshot,
            signal,
            observation.account,
            observation.positions,
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
        executor: MT5TradeExecutor,
        short_term: ShortTermMemory | None = None,
        trade_memory: TradeMemory | None = None,
        strategy_memory: StrategyMemory | None = None,
        world_memory: WorldMemory | None = None,
        candle_count: int = 50,
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
        self._stop = threading.Event()
        self._cycles = 0

    @property
    def cycles_completed(self) -> int:
        return self._cycles

    def stop(self) -> None:
        """Request graceful shutdown (loop exits after the current cycle)."""
        self._stop.set()

    def run_cycle(self, symbol: str, timeframe: Timeframe) -> AgentCycle:
        """Execute one full lifecycle; never raises (failures become outcomes)."""
        cycle_id = new_cycle_id()
        started = datetime.now(UTC)
        outcomes: list[StageOutcome] = []
        state: dict[str, Any] = {"cycle_id": cycle_id}
        error = ""
        try:
            self._observe(symbol, timeframe, outcomes, state)
            if _failed(outcomes):
                return self._finish(cycle_id, symbol, timeframe, started, outcomes, error)
            self._strategy_memory_stage(outcomes, state)
            self._plan_stage(outcomes, state)
            self._supervise_stage(outcomes, state)
            self._execute_stage(outcomes, state)
            self._verify_stage(outcomes, state)
            self._memory_update_stage(outcomes, state)
        except Exception as exc:  # last-resort guard: cycle reports, never raises
            error = f"{type(exc).__name__}: {exc}"
            logger.exception("agent cycle failed")
        return self._finish(cycle_id, symbol, timeframe, started, outcomes, error)

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
            primary = signals[0]
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
            tick = observation.snapshot.tick
            spread_points: dict[str, float] = {}
            if tick is not None:
                spread_points[observation.snapshot.symbol] = tick.spread
            context = RiskContext(
                account=observation.account,
                positions=observation.positions,
                orders=observation.orders,
                spreads_points=spread_points,
                server_time=datetime.now(UTC),
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
        logger.info(
            "agent cycle %s %s",
            cycle_id,
            "ok" if not error and not _failed(outcomes) else "degraded",
            extra={"extra_fields": {"cycle": cycle_id, "symbol": symbol, "stages": len(outcomes)}},
        )
        return AgentCycle(
            cycle_id, symbol, timeframe.value, tuple(outcomes), started, finished, error
        )


def _failed(outcomes: list[StageOutcome]) -> bool:
    return any(o.status == StageStatus.FAILED for o in outcomes)


__all__ = ["ContextBuilder", "Observation", "Observer", "TradingAgent"]
