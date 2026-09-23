# Production hardening runbook (Phase 12)

How to operate the agent safely: observe health, recover from outages, shut
down cleanly, and never lose auditability. Defaults are demo-first; nothing
here enables live trading.

## Health

- Liveness: `GET /health` → `{"ok": true}` (process is up; says nothing else).
- Readiness: `GET /api/health` → `{"status": "HEALTHY|DEGRADED|UNHEALTHY",
  "healthy": bool, "components": {...}}` (served by `serve_dashboard.py`
  probes: mt5, market, memory, llm, executor).
- Rule: **process-alive ≠ healthy.** Do not trust a running process whose
  `/api/health` is not HEALTHY. UNHEALTHY = do not trade; DEGRADED =
  investigate (e.g. LLM unconfigured → HOLD-only mode, which is safe).

## MT5 disconnect / reconnect

1. The agent fails cycles safely on disconnect (OBSERVE FAILED, no orders).
2. Reconnect via `ConnectionService.reconnect(config, creds, verify=...)`.
3. **Before any execution after reconnect**, `verify()` must re-read account
   state, open positions, and pending orders and confirm the intent is still
   valid — never blind-submit after a drop.
4. Retries reuse the same `client_id`: completed attempts replay from the
   ledger instead of resending. An `UNKNOWN` record (timeout after submission)
   means *verify positions/orders first*; it is not proof of failure.

## LLM failures

Any LLM failure (timeout, rate limit, auth, malformed JSON, invalid schema,
provider down, network) degrades to a HOLD proposal with the reason recorded.
HOLD is NO-TRADE: supervisor approves it as a no-op and the executor maps it
to REJECTED without terminal calls. If you see repeated `Planner degraded to
HOLD` rationales, fix provider config — the system is safe but idle.

## Watchdog

Trips (latched UNHEALTHY) after `watchdog_max_consecutive_failures`
consecutive failures of one kind; stale market data (> `watchdog_stale_after_s`)
reports DEGRADED. While halted, the agent starts no new cycles and submits no
new trades, and in-flight work finishes. Recovery is manual:

1. Read the watchdog snapshot / logs (`audit_event=agent_cycle`, errors).
2. Fix the cause (terminal, network, provider key, disk for `data/memory.db`).
3. Restart the process (trip state is in-memory by design).

The watchdog never increases activity and never closes positions.

## Graceful shutdown

Order: stop new cycles (`stop()` / SIGINT/SIGTERM) → finish the in-flight
cycle → persist memory (`store.close()`) → disconnect MT5 → flush logs →
exit. `run_agent.py` and `serve_dashboard.py` both implement this.
**Shutdown never closes open positions** — manage them explicitly.

## Secrets & config

- Secrets live in environment / `.env` only (git-ignored). `.env.example` has
  placeholders. Invalid config fails fast with a clear error.
- Diagnose with `AppSettings.masked()` (keys redacted); logs scrub residual
  secrets automatically, but never log secrets on purpose.
- Keep `trading_mode=dry_run` (default). DEMO refuses REAL accounts. LIVE
  needs `execution_mode=live` **and** `MT5_AGENT_ENABLE_LIVE_TRADING=true`.

## Dashboard exposure

Read-only by construction (GET only; POST/PUT/DELETE/PATCH → 405; no action
endpoints; tracebacks never leak). Default bind is loopback (`127.0.0.1`).
There is **no authentication**: do not bind beyond localhost unless the
dashboard sits behind an authenticated reverse proxy/TLS. A non-loopback
bind logs an explicit warning at startup.

## Audit reconstruction

Structured JSON logs carry `audit_event` (`agent_cycle`, `order_submitted`,
`order_result`, `mt5 reconnected`, ...), plus the SQLite memory store
(proposals, supervisor decisions, executions, outcomes) and the executor
ledger (`client_id` → record). Together they reconstruct any incident:
what was seen → planned → approved/rejected → submitted → acknowledged.

## Deployment checklist

- [ ] `.env` present locally, never committed; file perms restricted
- [ ] `config/app.yaml` reviewed (demo-first; loopback dashboard)
- [ ] `GET /api/health` HEALTHY before unattended runs
- [ ] Logs shipped somewhere durable (stdout JSON)
- [ ] Operator knows: UNKNOWN → verify; halted watchdog → manual recovery;
      shutdown ≠ position close
