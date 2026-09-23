# Phase 01 — MT5 Connectivity

## Objective
Establish a safe, read-only MT5 connectivity layer behind domain interfaces:
initialize/login/shutdown, terminal + account snapshots, health checks, and
deterministic reconnect — with no trading functionality.

## Scope
In scope: domain models/ports/errors, MT5 adapter, connection service with
retry policy, mappers, guarded `MetaTrader5` import, unit tests with fakes,
live-terminal integration test (skipped by default), `scripts/check_mt5.py`.
Out of scope: market data, orders/positions, strategies, LLM, risk, execution.

## Architecture
```
domain/{errors,account,terminal,ports}.py   # pure, never imports MetaTrader5
application/connection_service.py           # RetryPolicy + ensure_connected/reconnect
infrastructure/mt5/{module,mappers,connection_adapter}.py  # only MT5-touching code
```
`MT5ConnectionPort` is the seam: polling/sync/execution concerns stay behind
it so an optional MQL5 event bridge can be added later without touching domain.

## Components
- `domain/errors.py`: `MT5Error`, `MT5NotAvailableError`, `MT5ConnectionError`,
  `MT5LoginError`, `MT5NotConnectedError`, `MT5DataError`.
- `domain/account.py`: `AccountInfo` (frozen dataclass).
- `domain/terminal.py`: `TerminalInfo`, `MT5Credentials` (masked repr),
  `ConnectionConfig`, `ConnectionHealth`.
- `domain/ports.py`: `MT5ConnectionPort` ABC.
- `infrastructure/mt5/module.py`: `load_mt5()` (Windows + install guard).
- `infrastructure/mt5/mappers.py`: `map_account_info/map_terminal_info`
  (namedtuple `_asdict` / mapping / attribute objects; `None` -> `MT5DataError`).
- `infrastructure/mt5/connection_adapter.py`: `MT5ConnectionAdapter`
  (injectable `mt5_module` fake for tests; thread-safe; idempotent disconnect;
  `check_health()` never raises).
- `application/connection_service.py`: `ConnectionService` + `RetryPolicy`
  (`ensure_connected` with retries, `reconnect`, read passthrough).
- `config/settings.py`: added `mt5_path` + `to_connection_config()`.
- `scripts/check_mt5.py`: read-only status probe (JSON output, exit 1 on failure).

## Interfaces
- `MT5ConnectionPort.connect(config, credentials=None) / disconnect() /`
  `is_connected() / get_account_info() / get_terminal_info() / check_health()`
- `ConnectionService.ensure_connected(config, credentials=None) -> ConnectionHealth`
  (raises last `MT5Error` after exhaustion), `reconnect(...)`, `health()`,
  `get_account()`, `get_terminal()`, `disconnect()`
- `load_mt5() -> module` (raises `MT5NotAvailableError`)
- `map_account_info(raw) -> AccountInfo`, `map_terminal_info(raw) -> TerminalInfo`

## Data Models
See Components: `AccountInfo(login, server, currency, balance, equity, margin,`
`free_margin, profit, leverage, trade_allowed, name)`, `TerminalInfo(company,`
`name, path, trade_allowed, connected, build, max_bars)`, `ConnectionHealth(`
`connected, trade_allowed, account_login, terminal_company, error, details)`.

## Configuration
- `config/app.yaml`: `mt5_path/mt5_timeout_ms/mt5_portable` (+ commented login/server).
- Env: `MT5_AGENT_MT5_LOGIN / MT5_AGENT_MT5_PASSWORD / MT5_AGENT_MT5_SERVER /`
  `MT5_AGENT_MT5_PATH / MT5_AGENT_MT5_TIMEOUT_MS / MT5_AGENT_MT5_PORTABLE`.
- Password comes from env only, never stored in settings/YAML, never logged
  (`MT5Credentials.__repr__` masks it; health records exclude it).
- Live-terminal integration test gate: `MT5_AGENT_RUN_LIVE_MT5_TESTS=true`.

## Error Handling
- No terminal/package: `MT5NotAvailableError` with install guidance.
- `initialize()==False`: `MT5ConnectionError` with `last_error()`.
- `login()==False`: `MT5LoginError` (shutdown attempted), credentials not echoed.
- Reads without connection: `MT5NotConnectedError`; `None` payloads: `MT5DataError`.
- `check_health()` never raises; service exhausts retries then raises last error
  (fail safely — callers must not trade without healthy connection).

## Security Considerations
Read-only phase: no order-sending code exists anywhere. Secrets via env only,
masked repr, excluded from logs/health. Trading stays disabled (`dry_run`
default enforced by Phase 00 settings).

## Testing Strategy
- Unit (no terminal): `test_mt5_mappers` (namedtuple/dict/namespace/None/bad-type),
  `test_mt5_adapter` (`FakeMT5`: connect/read/cred-login/init-fail/login-fail/
  unread-connected/None-payloads/health-never-raises/idempotent-disconnect/
  repr-masking), `test_connection_service` (retry-success/exhaustion/reconnect/
  policy-validation/passthrough), settings `mt5_path` coverage.
- Integration: `tests/integration/test_mt5_live.py` (marked `integration`,
  skipped unless `MT5_AGENT_RUN_LIVE_MT5_TESTS=true`; read-only; skips cleanly
  when terminal unavailable). CI runs `-m "not integration"`.

## Acceptance Criteria
- [x] MT5 connection can be tested (fakes + optional live test)
- [x] Connection failure handled cleanly (`MT5ConnectionError`, fail-safe health)
- [x] Account information retrievable (`get_account_info` + mapper)
- [x] Terminal information retrievable (`get_terminal_info` + mapper)
- [x] Tests exist (unit + integration)
- [x] Documentation exists (this doc + MT5 guide)

## Definition of Done
Acceptance boxes checked; `pytest/ruff/mypy` green; diff reviewed; focused
commit `feat(phase-01): ...` pushed to `origin/main`.

## Files Added
- `src/mt5_agent/domain/{errors,account,terminal,ports}.py`
- `src/mt5_agent/infrastructure/mt5/{__init__,module,mappers,connection_adapter}.py`
- `src/mt5_agent/application/connection_service.py`
- `tests/unit/{test_mt5_mappers,test_mt5_adapter,test_connection_service}.py`
- `tests/integration/test_mt5_live.py`
- `scripts/check_mt5.py`

## Files Modified
- `src/mt5_agent/domain/__init__.py` (exports)
- `src/mt5_agent/application/__init__.py` (exports)
- `src/mt5_agent/infrastructure/__init__.py` (docstring)
- `src/mt5_agent/config/settings.py` (`mt5_path`, `to_connection_config`)
- `config/app.yaml`, `.env.example` (MT5 options)
- `docs/mt5/integration.md`, `README.md`, `ROADMAP.md`, `CHANGELOG.md`

## Dependencies
Runtime: `MetaTrader5>=5.0.45; sys_platform=='win32'` (optional `mt5` extra;
verified installed v5.0.6180 in dev env; never imported by domain/app).
No new mandatory dependencies.

## Future Work
Phase 02: market-data layer (`Tick/Candle/MarketSnapshot/SymbolInfo`,
`MarketDataProvider` on top of this connection, strategy consumes domain models).
