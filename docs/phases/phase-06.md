# Phase 06 — Planner

## Objective
Turn structured context (market state, strategy signal, account state, open
positions, memory notes) into a validated `TradeProposal` via an LLM — with
strict output validation, HOLD fallback, and a hard guarantee: the Planner
never executes orders.

## Scope
In scope: `PlannerInput/MemoryNote/TradeAction/TradeProposal` models,
`Planner` ABC, `LLMPlanner` (prompt + validate + fallback), unit tests on
fake providers, `scripts/check_plan.py` (offline `--stub` + live LLM).
Out of scope: memory store (Phase 09), Supervisor/risk (Phase 07),
execution (Phase 08).

## Architecture
```
domain/planning.py   # MemoryNote/PlannerInput/TradeAction/TradeProposal
ai/planner.py        # Planner ABC, LLMPlanner, SYSTEM_PROMPT,
                     # build_user_prompt(), validate_proposal(), hold_proposal()
```
`LLMPlanner(provider)` wraps any Phase 05 `LLMProvider`. Prompt = fixed
JSON-only system contract + deterministic JSON user context (last 20 candles,
tick, signal+facts, account, positions, memory). Response must parse as a
JSON object and pass `validate_proposal()`; anything else -> HOLD.

## Components
- `PlannerInput(symbol,timeframe,snapshot,signal,account?,open_positions,
  memory)` with cross-model symbol consistency checks.
- `TradeProposal(action,symbol,confidence,rationale,strategy,setup_id?,
  entry?,stop_loss?,take_profit?,risk_pct,volume?,provider?,model?,
  latency_ms?)` + `is_actionable`; HOLD carries no entry/volume.
- `LLMPlanner.plan()`: build prompt -> `provider.generate(json)` ->
  `validate_proposal()`; catches everything into HOLD (LLM errors named).
- `validate_proposal()`: action enum, BUY=`SL<entry<TP` /
  SELL=`TP<entry<SL`, entry+SL+TP required when directional, non-empty
  rationale, confidence 0..1, risk 0..100; setup/strategy copied from signal,
  provider metadata attached for audit.

## Interfaces
- `Planner.plan(input) -> TradeProposal`
- `build_user_prompt(input) -> str` (deterministic JSON)
- `validate_proposal(data, input, *, provider, model, latency_ms)`
- `hold_proposal(input, rationale) -> TradeProposal`

## Data Models
See Components. `MemoryNote(kind,text)` is intentionally minimal — Phase 09
replaces the tuple with store-backed retrieval without changing the Planner.

## Configuration
No new settings (reuses `llm_*`). Probe:
`python scripts/check_plan.py --stub` (offline, mirrors signal) or without
`--stub` for the configured provider. No execution flags exist anywhere.

## Error Handling
LLM timeout/API/parse errors, non-object JSON, invalid action, missing
entry/SL/TP, inverted brackets, empty rationale, out-of-range numbers — all
degrade to `HOLD` with the cause in `rationale`. `PlannerInput` construction
errors (symbol mismatch) raise immediately — fail fast before any LLM call.

## Security Considerations
Planner output is advisory; it cannot reach MT5 (source-checked: no
`order_send/order_check/positions_get/MetaTrader5` in `ai/planner.py`).
Risk limits are NOT enforced here — that is the Supervisor's job (Phase 07);
the Planner merely proposes within sane shapes.

## Testing Strategy
- `test_planning_models`: proposal/input/memory validation.
- `test_planner`: `FakeProvider` — valid BUY/SELL, inverted-bracket HOLD,
  malformed HOLD, provider-error HOLD, validator rejections, prompt content +
  system contract, `hold_proposal`, ABC check, no-execution source assertion.

## Acceptance Criteria
- [x] `Planner` + `LLMPlanner` exist
- [x] Market + signal + account + positions + memory input supported
- [x] `TradeProposal` has action/symbol/entry/SL/TP/risk/rationale/confidence/strategy+setup
- [x] Planner never executes (interface + source-tested)

## Definition of Done
Boxes checked; `pytest/ruff/mypy` green; stub probe verified live-market;
diff reviewed; focused commit `feat(phase-06): ...` pushed.

## Files Added
- `src/mt5_agent/domain/planning.py`
- `src/mt5_agent/ai/planner.py`
- `tests/unit/{test_planning_models,test_planner}.py`
- `scripts/check_plan.py`

## Files Modified
- `src/mt5_agent/domain/__init__.py`, `src/mt5_agent/ai/__init__.py`
- `README.md`, `ROADMAP.md`, `CHANGELOG.md`, `pyproject.toml` (v0.7.0)

## Dependencies
None new.

## Future Work
Phase 07: `Supervisor` + deterministic `RiskEngine` (max risk/exposure/
positions, daily loss, symbol/session/spread gates, mandatory SL/TP,
duplicates, cooldowns) — the safety boundary the Planner cannot cross.
