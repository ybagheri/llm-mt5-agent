# Phase 12 — Production Hardening

## Objective
Make the Phase 00–11 system robust, observable, recoverable, testable, and safe
without changing its architecture: supervised LLM planner, deterministic risk
boundary, demo-first execution. Safety and deterministic behavior around trade
execution take priority over convenience. No live trading is introduced.

## Scope
In scope: structured audit logging with secret scrubbing; HEALTHY/DEGRADED/
UNHEALTHY health aggregation + `GET /api/health`; retry backoff; MT5 reconnect
with post-reconnect verification; LLM-failure → HOLD proof; `UNKNOWN`
execution state for ambiguous outcomes; graceful-shutdown ordering; fail-safe
watchdog (halt-only); secrets review; dashboard exposure review (stays
read-only, loopback, unauthenticated-by-design); hardening tests; CI
dependency audit; operations runbook.
Out of scope: live trading, new strategies, dashboard actions/auth,
persistent execution ledger, metrics backends.

## Architecture
```
logging_utils.py   # SecretScrubbingFilter + audit(event, **fields)
application/
  health.py        # HealthStatus / ComponentHealth / SystemHealth / HealthService
  watchdog.py      # WatchdogConfig / Watchdog (halt-only, latched trip)
  connection_service.py  # RetryPolicy.backoff_factor/max_delay + reconnect(verify=)
  agent.py         # optional Watchdog: skips new cycles when halted, reports outcomes
execution/executor.py    # UNKNOWN on timeout/transport ambiguity + audit events
domain/execution.py      # ExecutionStatus.UNKNOWN
dashboard/app.py         # GET /api/health + non-loopback bind warning
scripts/run_agent.py     # Watchdog wiring + ordered shutdown logs
scripts/serve_dashboard.py  # HealthService probes -> /api/health
```

## Components
- **Audit logging**: `audit(logger, event, **fields)` emits one JSON record with
  `audit_event`, `ts`, and scrubbed fields. Events: `agent_cycle`,
  `order_submitted`, `order_result`, `mt5 reconnected`, post-reconnect
  verification. `SecretScrubbingFilter` (installed by `configure_logging()`)
  redacts secret-like keys and inline `key=value` / `Bearer` tokens as a second
  line of defense — callers still must not log secrets.
- **Health**: `HealthService` runs injected probes (never raises; a raising
  probe becomes UNHEALTHY) and aggregates worst-wins. Empty probe set is
  UNHEALTHY (nothing verified). `SystemHealth.to_dict()` feeds `/api/health`.
  Liveness `GET /health` (`{"ok": true}`) is unchanged.
- **Retry**: `RetryPolicy` gains `backoff_factor` (≥1.0) and
  `max_delay_seconds`; `delay_for(attempt)` is deterministic (no jitter).
  Default `backoff_factor=1.0` preserves the legacy fixed delay.
- **Reconnect**: `reconnect(..., verify=...)` disconnects (best effort),
  reconnects, logs, then runs `verify()` — the caller re-reads account state,
  open positions, and pending orders and raises when the intent is stale.
  Execution after reconnect without verification is a safety violation.
- **Idempotency**: ledger replay on `client_id` is unchanged (in-memory); new
  `UNKNOWN` status marks ambiguous outcomes (timeout/transport error after a
  possible submission). UNKNOWN must be verified (positions/orders) before any
  retry with the same `client_id`; it is never treated as failure.
- **Watchdog**: `Watchdog` counts consecutive failures per kind, tracks market
  freshness via `note_observation()`, trips (latched) at
  `max_consecutive_failures` → UNHEALTHY/`should_halt()`. Stale data → DEGRADED
  (no halt). `reset()` is manual (operator reviewed). The agent refuses new
  cycles and breaks `run()` when halted; it never closes positions.

## Interfaces
- `audit(logger, event, **fields)`, `scrub_value()`, `scrub_message()`
- `HealthService(probes).check() -> SystemHealth`; `overall()`
- `RetryPolicy.delay_for(attempt)`; `ConnectionService.reconnect(config, creds, verify=...)`
- `ExecutionStatus.UNKNOWN`; ledger replay unchanged
- `Watchdog.note_success/note_failure/note_observation/reset/status/should_halt/snapshot`
- `TradingAgent(..., watchdog=None)` (optional, backward compatible)
- `GET /api/health` → `SystemHealth.to_dict()` (or UNKNOWN-when-unwired)
- `is_loopback(host)`; non-loopback bind logs a warning

## Data Models
`ComponentHealth(name, status, message, latency_ms?)`, `SystemHealth(status,
components, checked_at)` with `healthy` (all-HEALTHY) and `to_dict()`;
`WatchdogConfig(max_consecutive_failures=5, stale_after_s=300.0)`.

## Configuration
New settings (safe defaults, env-overridable, validated):
- `watchdog_max_consecutive_failures` (5; 1..100)
- `watchdog_stale_after_s` (300.0; ≥0)
`config/app.yaml` + `.env.example` document them. Live-trading dual gate is
untouched (`live` still requires `MT5_AGENT_ENABLE_LIVE_TRADING=true`).

## Error Handling
- LLM timeout/rate-limit/auth/malformed/invalid-schema/provider-down/network:
  `LLMPlanner` degrades to HOLD (confidence 0, reason recorded); executor maps
  HOLD and supervisor rejections to REJECTED without terminal calls. Safe
  behavior is NO-TRADE (HOLD), never a guessed decision.
- MT5 failures: connect/reconnect raise after exhaustion (callers must not
  trade); executor maps disconnect → FAILED with re-verify guidance and
  timeouts → UNKNOWN.
- Health/watchdog/dashboard probes never raise into serving paths.

## Security Considerations
Secrets review passed: `.env` git-ignored (only `.env.example` tracked); no
hardcoded credentials/keys/tokens in the tree (grep-verified); passwords/API
keys flow env → `MT5Credentials`/headers only, masked in `repr`/`masked()`,
scrubbed in logs. Dashboard stays read-only (mutating verbs → 405), loopback
by default, no auth layer — do not bind beyond localhost without an
authenticated reverse proxy (non-loopback bind now warns). Default remains
`dry_run`; DEMO refuses REAL accounts; LIVE needs the dual opt-in.
Dependency audit (`pip-audit`) is clean; CI runs it on every build.

## Testing Strategy
New `tests/unit/test_hardening.py` (fakes only): secret scrubbing (nested,
inline, emitted JSON), audit shape, health aggregation + probe-failure
containment, backoff schedule + validation, reconnect verify (called /
failure blocks), timeout → UNKNOWN + ledger replay without resend,
disconnect guidance, LLM-timeout → HOLD, watchdog trip/halt/reset/stale,
agent halt integration, `/api/health` (+ liveness contract intact, double
`stop()` idempotent), loopback detection, watchdog settings + live-gate
invariants. Full suite: `pytest -m "not integration" -q`; `ruff check src
tests scripts`; `ruff format --check src tests`; `mypy src`.

## Acceptance Criteria
- [x] Audit events reconstruct startup/cycles/orders/reconnects; secrets scrubbed
- [x] Health distinguishes HEALTHY/DEGRADED/UNHEALTHY; served via `/api/health`
- [x] Reconnect requires verification before execution; duplicates prevented
- [x] Every LLM failure mode degrades to HOLD (NO-TRADE)
- [x] UNKNOWN outcomes force verify-before-retry with the same `client_id`
- [x] Graceful shutdown ordered (stop cycles → persist → disconnect → flush)
- [x] Watchdog halts new activity only; never escalates or closes positions
- [x] Secrets review + dashboard exposure review documented
- [x] CI green incl. dependency audit; docs updated

## Definition of Done
Boxes checked; `pytest/ruff/mypy` green; read-only MT5 probe still connects;
diff reviewed; focused commit `feat(phase-12): ...` on `main`.

## Files Added
- `src/mt5_agent/application/health.py`
- `src/mt5_agent/application/watchdog.py`
- `tests/unit/test_hardening.py`
- `docs/operations/hardening.md`

## Files Modified
- `src/mt5_agent/logging_utils.py` (scrub filter + `audit()`)
- `src/mt5_agent/application/connection_service.py` (backoff + `verify`)
- `src/mt5_agent/application/agent.py` (optional watchdog + audit)
- `src/mt5_agent/application/__init__.py` (exports)
- `src/mt5_agent/domain/execution.py` (`UNKNOWN`)
- `src/mt5_agent/execution/executor.py` (UNKNOWN + audit)
- `src/mt5_agent/dashboard/app.py` (`/api/health`, loopback warning)
- `src/mt5_agent/config/settings.py`, `config/app.yaml`, `.env.example`
- `scripts/run_agent.py`, `scripts/serve_dashboard.py`
- `.github/workflows/ci.yml`, `pyproject.toml` (v0.13.0)
- `src/mt5_agent/__init__.py` (v0.13.0)
- `README.md`, `ROADMAP.md`, `CHANGELOG.md`

## Dependencies
New (CI/dev-time only): `pip-audit` (installed in CI, not a runtime dep).
Runtime deps unchanged (`pyyaml`, `pydantic`, `pydantic-settings`,
`python-dotenv`).

## Future Work
Persistent execution ledger (survive restarts); metrics/alerting sink;
dashboard auth for non-loopback deployments; circuit breakers per symbol;
chaos-style reconnect drills as integration tests. Live trading stays
disabled pending explicit opt-in and review.
