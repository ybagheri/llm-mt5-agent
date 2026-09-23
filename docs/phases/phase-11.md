# Phase 11 — Dashboard

## Objective
Serve a lightweight read-only web dashboard over account, market, agent,
risk, memory, and LLM state — stdlib HTTP only (no web framework), GET-only
(no actions exist to invoke), safe to expose on loopback by default.

## Scope
In scope: `DashboardState` sections, `DashboardStateProvider`,
`estimate_cost_usd`, `DashboardApp`/`DashboardHandler`, settings wiring,
unit + HTTP contract tests, `scripts/serve_dashboard.py`.
Out of scope: interactivity/mutations (explicitly refused with 405),
advanced frontend, auth (loopback-only default; Phase 12 deployment notes).

## Architecture
```
dashboard/
  state.py     # Account/Market/Agent/Risk/Memory/LLM sections + to_dict()
  provider.py  # assembles sections from services (best-effort per section)
  costs.py     # static per-model USD/1M table (unknown -> None, never invented)
  app.py       # ThreadingHTTPServer: / (HTML), /api/state (JSON), /health
```
Provider reads only; every section degrades independently (core failure ->
`{"error": ...}` state, HTTP 200 with error field; build crashes -> 500 JSON).

## Components
- Sections per spec: account (balance/equity/margin/day P&L), market
  (symbol/price/spread/timeframe/session), agent (state/signal/proposal),
  risk (limits/exposure/positions), memory (decisions/trades/events), LLM
  (provider/model/latency/tokens/estimated cost).
- Day P&L = today's realized (history since UTC midnight) + floating;
  `None` when history unavailable.
- `record_llm(response)` hook feeds the LLM section (usage + cost).
- HTML page fetches `/api/state` on `dashboard_refresh_s` interval.

## Interfaces
- `DashboardStateProvider.build(symbol, timeframe) -> DashboardState`
- `DashboardStateProvider.record_llm(response)`
- `DashboardApp.start() -> url` / `.stop()` / `.url`
- `GET /`, `GET /api/state?symbol=&timeframe=`, `GET /health`

## Data Models
See Components. All JSON-serializable via `to_dict()` (`default=str` fallback).

## Configuration
- `dashboard_host` (default 127.0.0.1), `dashboard_port` (8080, 0 = ephemeral
  in tests), `dashboard_refresh_s` (15); env `MT5_AGENT_DASHBOARD_*`.
- Serve: `serve_dashboard.py [--host …] [--port …]` (blocks until Ctrl+C).

## Error Handling
Unknown timeframe -> 400 JSON; unknown path -> 404; POST/PUT/DELETE/PATCH ->
405 `{"error": "read-only"}`; provider crashes -> 500 JSON (no tracebacks).

## Security Considerations
Read-only by construction (no mutating routes/handlers); binds loopback by
default; no auth layer yet — do not expose beyond localhost before Phase 12
review. No secrets in state (account numbers are terminal-reported identifiers
shown locally, matching existing probe behavior).

## Testing Strategy
- `test_dashboard`: section values incl. spread-points math, core-failure
  error state, memory listing, LLM usage + cost math, unknown-model None,
  live HTTP contract (health/state/HTML/405×4/404/400) on ephemeral port.

## Acceptance Criteria
- [x] Account/market/agent/risk/memory/LLM sections served
- [x] Lightweight (stdlib only, single page + JSON API)
- [x] Read-only (mutating verbs refused, no action endpoints)

## Definition of Done
Boxes checked; `pytest/ruff/mypy` green; served + curled live; diff reviewed;
focused commit `feat(phase-11): ...` pushed.

## Files Added
- `src/mt5_agent/dashboard/{state,provider,costs,app}.py`
- `tests/unit/test_dashboard.py`
- `scripts/serve_dashboard.py`

## Files Modified
- `src/mt5_agent/dashboard/__init__.py`
- `src/mt5_agent/config/settings.py`, `config/app.yaml`, `.env.example`
- `README.md`, `ROADMAP.md`, `CHANGELOG.md`, `pyproject.toml` (v0.12.0)

## Dependencies
None new.

## Future Work
Phase 12: hardening (audit logs, health/watchdog, reconnect + retry policies,
timeouts, idempotency review, secrets review, CI/coverage, deployment docs
incl. dashboard exposure guidance). Live stays disabled unless explicitly enabled.
