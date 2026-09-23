# Phase 09 — Memory System

## Objective
Persist compact structured records of observations, signals, proposals,
verdicts, executions, and outcomes behind a backend-agnostic `MemoryStore`
(SQLite first), split into short-term / trade / strategy / world scopes with
enforced retention — memory as a rolling window, never a transcript dump.

## Scope
In scope: `MemoryRecord/MemoryKind/MemoryScope` models, `MemoryStore` ABC,
`SQLiteMemoryStore`, four scoped facades, settings wiring, unit tests,
`scripts/check_memory.py`.
Out of scope: vector/RAG memory, agent-loop wiring (Phase 10 reads these
facades), dashboard views (Phase 11).

## Architecture
```
domain/memory.py     # MemoryRecord (capped summary + whitelisted data dict)
memory/store.py      # MemoryStore ABC (append/recent/count/prune/close)
memory/sqlite_store.py  # stdlib sqlite3, WAL, thread lock, :memory: for tests
memory/memories.py   # ShortTerm/Trade/World/StrategyMemory facades
```
Facades own one scope each and prune to `keep_last` on every append.
PostgreSQL later implements the same four methods — domain code is untouched.

## Components
- Kinds: `market_observation, strategy_signal, trade_proposal,
  supervisor_decision, execution, outcome, strategy_note, world_note`,
  each mapped to its scope via `MemoryKind.scope()`.
- `ShortTermMemory.record_observation(snapshot)` — close/bid/ask + count.
- `TradeMemory.record_proposal/decision/execution/outcome` — action/confidence/
  brackets, verdict codes, ticket/slippage/error only (no raw envelopes).
- `StrategyMemory.record_signal/note`, `WorldMemory.note` — identifiers +
  capped facts (first 12 keys).
- Summaries clipped to 280 chars (`…` marker); `MemoryRecord` rejects longer.

## Interfaces
- `MemoryStore.append(record) -> row id`
- `MemoryStore.recent(scope, *, limit, symbol?, kind?, since?)` (newest first)
- `MemoryStore.count(scope)`, `MemoryStore.prune(scope, keep_last)`
- Facade `recent(limit, **filters)`, `count()`, `record_*` writers

## Data Models
`MemoryRecord(scope,kind,summary<=280,symbol,data,created_at,row id?)`.
SQLite table `memory_records` with `(scope, id)` + `symbol` indexes.

## Configuration
- `memory_db_path` (default `data/memory.db`, `MT5_AGENT_MEMORY_DB_PATH`),
  per-scope keeps (`memory_*_keep`, env-overridable). `data/` is git-ignored.
- Probe: `check_memory.py [--db path] [--scope x] [--limit n] [--demo]`.

## Error Handling
Validation errors (empty/oversize summaries, bad limits) raise immediately;
malformed stored rows degrade (empty data, current timestamp) rather than
crash reads. Store `close()` is idempotent-safe via lock discipline.

## Security Considerations
Local file only, no network; records carry no credentials (writers whitelist
numeric/enum fields — proposals log risk/confidence, never keys).

## Testing Strategy
- `test_memory_store`: append/recent/count, symbol/kind/since filters,
  newest-first, prune keeps newest, file persistence across reopen, model +
  scope-mapping validation.
- `test_memories`: observation/proposal/decision/execution/outcome writers,
  kind coverage, notes, retention enforcement, 280-char cap.

## Acceptance Criteria
- [x] `MemoryStore` abstraction exists (SQLite first)
- [x] `ShortTerm/Trade/World/StrategyMemory` exist
- [x] Observations, decisions, proposals, verdicts, executions, outcomes stored
- [x] Compact records enforced (caps + whitelists + retention)
- [x] PostgreSQL-replaceable (ABC contract, no backend leakage)

## Definition of Done
Boxes checked; `pytest/ruff/mypy` green; probe verified on real file;
diff reviewed; focused commit `feat(phase-09): ...` pushed.

## Files Added
- `src/mt5_agent/domain/memory.py`
- `src/mt5_agent/memory/{store,sqlite_store,memories}.py`
- `tests/unit/{test_memory_store,test_memories}.py`
- `scripts/check_memory.py`

## Files Modified
- `src/mt5_agent/domain/__init__.py`, `src/mt5_agent/memory/__init__.py`
- `src/mt5_agent/config/settings.py`, `config/app.yaml`, `.env.example`
- `docs/memory/design.md`, `README.md`, `ROADMAP.md`, `CHANGELOG.md`,
  `pyproject.toml` (v0.10.0)

## Dependencies
None new (stdlib `sqlite3`).

## Future Work
Phase 10: orchestrator records every lifecycle stage through these facades
and feeds `recent()` excerpts to the Planner as `MemoryNote`s.
