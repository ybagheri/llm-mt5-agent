# Phase 08 — Execution Engine

## Objective
Execute only Supervisor-approved proposals through a strict lifecycle with
full audit records. DRY_RUN simulates without terminal calls; DEMO trades
demo accounts only (refused on real accounts); LIVE is unreachable without
explicit dual opt-in.

## Scope
In scope: `ExecutionMode/OrderRequest/ExecutionRecord` models,
`TradeExecutor` ABC, `MT5TradeExecutor` (6-stage lifecycle + idempotency
ledger), settings wiring, unit tests on fakes, `scripts/check_execute.py`.
Out of scope: strategy/agent orchestration (Phase 10), memory of fills
(Phase 09 consumes records).

## Architecture
```
domain/execution.py      # ExecutionMode, OrderRequest, ExecutionStatus, Record
execution/executor.py    # TradeExecutor ABC + MT5TradeExecutor
```
`execute(decision, *, client_id?)`: replay ledger on `client_id` hit, else
validate -> prepare -> order_check -> execute -> verify -> record. The
executor accepts `SupervisorDecision`, never a raw proposal — unapproved and
HOLD decisions become REJECTED records without terminal contact.

## Components
- `OrderRequest(symbol, BUY|SELL, volume, SL, TP, magic, comment, deviation,
  client_id)` — normalized intent; HOLD rejected at construction.
- `MT5TradeExecutor(mode=DRY_RUN, allow_live=False, connection?, mt5?,
  default_volume, magic, deviation)` + `ledger` replay map.
- Stage guards: rejected/HOLD -> REJECTED; LIVE without `allow_live` ->
  REJECTED; DEMO on `trade_mode == REAL` -> REJECTED; offline/no-tick ->
  FAILED; `order_check`/`order_send` non-DONE retcodes -> FAILED with
  `error_code`; DONE -> SUCCESS with ticket/deal/prices/slippage; verify via
  `positions_get(ticket=)` is best-effort (never downgrades DONE).
- Slippage = executed − requested (signed); comment tags `client_id` prefix.

## Interfaces
- `TradeExecutor.execute(decision, *, client_id?) -> ExecutionRecord`
- `MT5TradeExecutor.mode / .ledger` (copies)

## Data Models
`ExecutionRecord(client_id,symbol,action,volume,status,mode,ticket?,deal?,
executed/requested_price,slippage?,error_code,message,decided_at)` — every
attempt auditable, including rejections and dry runs.

## Configuration
- `execution_mode: dry_run|demo|live` (default dry_run; `live` needs
  `MT5_AGENT_ENABLE_LIVE_TRADING=true` like `trading_mode`).
- `execution_default_volume/magic/deviation`; env `MT5_AGENT_EXECUTION_*`.
- Executor `allow_live` defaults False — settings opt-in alone is not enough
  programmatically; Phase 10+ wires it deliberately.
- Probe: `check_execute.py [--mode dry_run|demo]` (no LIVE option exists).

## Error Handling
Market/terminal failures become FAILED records (never raise). Unknown
account mode fails closed for DEMO. Retries with the same `client_id`
replay the stored record — duplicates impossible by retry.

## Security Considerations
Dual live gate (settings flag + `allow_live=True`), DEMO-vs-REAL account
check, HOLD/rejected short-circuit before any MT5 call, DRY_RUN default.
No credentials in records (comment carries only a `client_id` prefix).

## Testing Strategy
- `test_execution_models`: request/record validation incl. ticket rule.
- `test_executor`: `FakeMT5` — dry-run silence, rejected/HOLD short-circuit,
  LIVE block, verified SUCCESS + slippage, DEMO-on-real refusal, check/send
  failure codes, idempotent replay (send called once), offline/no-tick,
  unverified-fill honesty. Settings live-gate test.

## Acceptance Criteria
- [x] `TradeExecutor` + `MT5TradeExecutor` exist
- [x] validate→prepare→order_check→execute→verify→record lifecycle
- [x] DRY_RUN + DEMO supported; LIVE never the default
- [x] Idempotent retries (no duplicate submission)
- [x] request/response/ticket/time/slippage/error/status recorded

## Definition of Done
Boxes checked; `pytest/ruff/mypy` green; dry-run probe verified live-market;
diff reviewed; focused commit `feat(phase-08): ...` pushed.

## Files Added
- `src/mt5_agent/domain/execution.py`
- `src/mt5_agent/execution/executor.py`
- `tests/unit/{test_execution_models,test_executor}.py`
- `scripts/check_execute.py`

## Files Modified
- `src/mt5_agent/domain/{account,__init__}.py` (`trade_mode`)
- `src/mt5_agent/infrastructure/mt5/mappers.py` (map `trade_mode`)
- `src/mt5_agent/execution/__init__.py`
- `src/mt5_agent/config/settings.py` (execution block + live gate)
- `config/app.yaml`, `.env.example`, `tests/unit/test_settings.py`
- `README.md`, `ROADMAP.md`, `CHANGELOG.md`, `pyproject.toml` (v0.9.0)

## Dependencies
None new.

## Future Work
Phase 09: memory store persisting proposals/verdicts/records/outcomes as
compact structured rows (SQLite first).
