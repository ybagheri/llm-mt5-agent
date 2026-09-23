# Phase 04 — Strategy Engine

## Objective
Provide a generic, deterministic strategy abstraction over Phase 02/03 domain
models: objective market facts in, `StrategySignal` out. Ship an
observation-only `NullStrategy` plus an extensible measured-move breakout
reader. No LLM involvement by design.

## Scope
In scope: `Strategy` ABC, `MarketContext/StrategyContext`, `StrategySignal`,
`StrategyDecision`, `Setup`, `NullStrategy`, `MeasureMoveStrategy` +
`DonchianBreakoutStrategy`, `StrategyService` + triage, unit tests, gated live
test, `scripts/check_strategy.py`.
Out of scope: LLM planning (Phase 05/06), risk/execution, memory.

## Architecture
```
domain/strategy.py            # Direction/DecisionAction/Setup/MarketContext/
                              # StrategySignal/StrategyDecision (+Context alias)
strategies/
  base.py                     # Strategy.analyze(context) ABC
  null_strategy.py            # observation-only baseline
  measure_move.py             # MeasureMoveStrategy pipeline + DonchianBreakout
application/strategy_service.py  # multi-strategy fan-out + triage decisions
```
Strategies read `MarketContext(snapshot, account_state?)` only — no MT5, no
HTTP, no LLM imports anywhere in `domain/` or `strategies/`.

## Components
- `Strategy.analyze(context: MarketContext) -> StrategySignal` (pure).
- `NullStrategy`: always `FLAT`/0.0, facts `{candles, latest_close, mode}`.
- `MeasureMoveStrategy(params)`: lookback structure-break pipeline —
  prior N−1 high/low, impulse range, latest-close break -> `LONG/SHORT`,
  else `FLAT` with `skip` reason; hooks `confirm/confidence_of/setup_for`
  let subclasses specialize without forking the pipeline.
- `DonchianBreakoutStrategy`: concrete N-bar reader (default lookback 20).
- `MeasureMoveParams(lookback, min_candles, breakout_confidence)` validated.
- `StrategyService(strategies)`: `analyze()` fan-out (failing strategy ->
  FLAT error signal, fail safely), `decide()` triage: directional ->
  `CANDIDATE`, flat-with-setups -> `OBSERVE`, else `SKIP`.

## Interfaces
- `Strategy.analyze(context) -> StrategySignal`
- `StrategyService.analyze(context) -> list[StrategySignal]`
- `StrategyService.decide(context) -> list[StrategyDecision]`
- `triage(signal) -> StrategyDecision` (pure rule)

## Data Models
`Setup(identifier,name,direction,confidence,description)`,
`MarketContext(symbol,timeframe,snapshot,account_state?,built_at)`,
`StrategySignal(strategy,symbol,timeframe,direction,confidence,setups,facts,
rationale,generated_at)`, `StrategyDecision(action,reasons,signal)`.

## Configuration
Probe flags only: `check_strategy.py --symbol/--timeframe/--count/--lookback`
(defaults from `mt5_default_*` settings). Strategy params are constructor
args, future YAML-bound in agent config (Phase 10).

## Error Handling
Short data -> `FLAT` + `skip` fact (not an exception). Strategy exceptions are
contained per-strategy into FLAT error signals; service never fails the batch.
Model validators reject empty symbols, mismatched snapshot/context symbols,
and out-of-range confidence.

## Security Considerations
No credentials, no orders, no network. Signals are advisory facts for the
later Planner/Supervisor chain; nothing here can trade.

## Testing Strategy
- `test_strategy_models`: setup/context/signal/decision validation.
- `test_strategies`: synthetic candles — long/short breakouts, range flat,
  insufficient-data flat, `confirm()` veto, params validation, ABC check.
- `test_strategy_service`: fan-out order, CANDIDATE/SKIP triage, failure
  degradation, empty-registry rejection, OBSERVE branch.
- `test_strategy_live`: gated, 30-candle EURUSD snapshot through both
  strategies, Null invariant asserted live.

## Acceptance Criteria
- [x] `Strategy.analyze(MarketContext)` abstraction exists
- [x] `StrategyContext/MarketContext/StrategySignal/StrategyDecision/Setup` exist
- [x] `NullStrategy`/observation-only exists
- [x] `MeasureMoveStrategy` abstraction exists (concrete Donchian reader)
- [x] No LLM dependency in strategy code
- [x] Objective market facts computed deterministically

## Definition of Done
Boxes checked; `pytest/ruff/mypy` green; live probe verified; diff reviewed;
focused commit `feat(phase-04): ...` pushed.

## Files Added
- `src/mt5_agent/domain/strategy.py`
- `src/mt5_agent/strategies/{base,null_strategy,measure_move}.py`
- `src/mt5_agent/application/strategy_service.py`
- `tests/unit/{test_strategy_models,test_strategies,test_strategy_service}.py`
- `tests/integration/test_strategy_live.py`
- `scripts/check_strategy.py`

## Files Modified
- `src/mt5_agent/strategies/__init__.py`
- `src/mt5_agent/domain/__init__.py`
- `src/mt5_agent/application/__init__.py`
- `docs/strategy/engine.md`, `README.md`, `ROADMAP.md`, `CHANGELOG.md`,
  `pyproject.toml` (v0.5.0)

## Dependencies
None new.

## Future Work
Phase 05: provider-agnostic LLM layer (`LLMProvider`, structured output,
usage/latency tracking) — strategies stay LLM-free; the Planner consumes
signals + context.
