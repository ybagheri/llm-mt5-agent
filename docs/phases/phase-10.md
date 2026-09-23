# Phase 10 — Agent Orchestrator

## Objective
Wire every layer into one observable lifecycle — OBSERVE → CONTEXT →
STRATEGY → MEMORY → PLAN → SUPERVISE → EXECUTE → VERIFY → MEMORY UPDATE —
as explicit stage methods (never one giant loop), with per-stage outcomes,
memory writes at each step, and graceful shutdown.

## Scope
In scope: `Stage/StageStatus/StageOutcome/AgentCycle` models, `Observer`,
`ContextBuilder`, `TradingAgent` (`run_cycle` + looping `run` + `stop`),
agent settings, unit tests on fakes, gated live dry-run cycle,
`scripts/run_agent.py` (one-shot, `--loop`, signal handling).
Out of scope: dashboard (Phase 11), hardening (Phase 12).

## Architecture
```
application/agent.py   # Observation, Observer, ContextBuilder, TradingAgent
domain/agent.py        # Stage/StageStatus/StageOutcome/AgentCycle/new_cycle_id
```
`Observer` reads (market/account/positions/orders); `ContextBuilder` shapes
`MarketContext`/`PlannerInput` (strategy signals + memory notes);
`TradingAgent` chains nine stage methods, each appending a `StageOutcome`.
Planner is optional (`None` -> HOLD); executor is mode-driven (DRY_RUN in
probes). Memory facades are optional collaborators — absent means "skip
writes", never failure.

## Components
- Stages: OBSERVE (snapshot+state, halts cycle on failure), CONTEXT (shape),
  STRATEGY (fan-out, record signal), MEMORY (pull planner notes),
  PLAN (LLM or HOLD fallback, record proposal), SUPERVISE (review + record),
  EXECUTE (approved directionals only, record), VERIFY (outcome check),
  MEMORY_UPDATE (observation + outcome writes).
- `run(symbols, timeframe, *, interval_s, max_cycles)`: round-robin until
  `stop()` / `max_cycles`; `stop()` sets the event the loop waits on.
- `run_agent.py`: settings wiring, SIGINT/SIGTERM -> `stop()`, JSON cycle
  report, exit 1 when any cycle degraded.

## Interfaces
- `Observer.observe(symbol, timeframe, count?) -> Observation`
- `ContextBuilder.build_context(observation) / build_planner_input(observation)
  / memory_notes(symbol)`
- `TradingAgent.run_cycle(symbol, timeframe) -> AgentCycle` (never raises)
- `TradingAgent.run(symbols, timeframe, *, interval_s?, max_cycles?)`
- `TradingAgent.stop()`

## Data Models
`StageOutcome(stage,status,summary,at,data)`, `AgentCycle(cycle_id,symbol,
timeframe,stages,started/finished_at,error)` + `.ok` / `.stage()` helpers.

## Configuration
- `agent_symbols` CSV (default EURUSD), `agent_interval_s` (default 60),
  `agent_candle_count` (default 50); env `MT5_AGENT_AGENT_*`.
- Probe: `run_agent.py [--symbols X] [--timeframe M1] [--cycles 1] [--loop]`
  reuses all `llm_*/risk_*/execution_*/memory_*` settings.

## Error Handling
`run_cycle` never raises: stage exceptions become FAILED outcomes, the
pipeline halts only where unsafe (post-OBSERVE), and a last-resort guard
captures anything else into `cycle.error`. Memory read/write failures log
and continue. Planner `None` degrades to HOLD (offline-capable agent).

## Security Considerations
Agent adds no new authority: planning stays advisory, Supervisor still gates,
executor still mode-gated. Loop mode cannot escalate modes by itself.

## Testing Strategy
- `test_agent`: fake ports + real services — full HOLD-path cycle (9 stages,
  skipped EXECUTE/VERIFY, memory counts), OBSERVE-failure degradation,
  `run()` max-cycles + `stop()`, settings parsing.
- `test_agent_live`: gated single dry-run cycle on demo (9 stages, `ok`).

## Acceptance Criteria
- [x] `TradingAgent/AgentCycle/Observer/ContextBuilder` exist
- [x] Full 9-stage lifecycle implemented
- [x] Every stage observable (`StageOutcome`) and testable (isolated methods)
- [x] Explicit objects, graceful shutdown (`stop()` + signal wiring)

## Definition of Done
Boxes checked; `pytest/ruff/mypy` green; live dry-run cycle verified;
diff reviewed; focused commit `feat(phase-10): ...` pushed.

## Files Added
- `src/mt5_agent/domain/agent.py`
- `src/mt5_agent/application/agent.py`
- `tests/unit/test_agent.py`
- `tests/integration/test_agent_live.py`
- `scripts/run_agent.py`

## Files Modified
- `src/mt5_agent/domain/__init__.py`, `src/mt5_agent/application/__init__.py`
- `src/mt5_agent/config/settings.py` (`agent_*` + parser), `config/app.yaml`,
  `.env.example`
- `README.md`, `ROADMAP.md`, `CHANGELOG.md`, `pyproject.toml` (v0.11.0)

## Dependencies
None new.

## Future Work
Phase 11: read-only dashboard over account/market/agent/risk/memory/LLM state
(consumes `AgentCycle` histories + memory stores).
