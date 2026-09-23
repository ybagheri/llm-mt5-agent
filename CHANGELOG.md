# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.13.0] - 2026-09-23

### Added
- Phase 12: production hardening (no architecture change, no live trading).
- Logging: `SecretScrubbingFilter` (defense-in-depth redaction) + `audit()`
  events (`agent_cycle`, `order_submitted`, `order_result`, reconnect).
- Health: `HealthStatus` (HEALTHY/DEGRADED/UNHEALTHY), `HealthService`
  (never-raising probes, worst-wins), `GET /api/health` on the dashboard
  (`/health` liveness unchanged); `serve_dashboard.py` wires live probes.
- Retry: `RetryPolicy` backoff (`backoff_factor`, `max_delay_seconds`,
  `delay_for()`; default preserves fixed delay).
- Reconnect: `reconnect(..., verify=...)` forces post-reconnect re-verification
  (account/positions/orders) before any execution.
- Execution: `ExecutionStatus.UNKNOWN` for ambiguous (timeout/transport)
  outcomes; verify-before-retry with the same `client_id`; disconnect records
  guide safe retry.
- Watchdog: halt-only `Watchdog` (consecutive-failure trip, stale-data
  degrade, manual reset); agent refuses new cycles + breaks `run()` when
  halted; wired in `run_agent.py` via new `watchdog_*` settings.
- Dashboard: non-loopback bind warning (`is_loopback()`); stays read-only.
- CI: `pip-audit` dependency audit; lint now covers `scripts/`.
- Tests: `tests/unit/test_hardening.py` (scrub/audit/health/backoff/
  reconnect/UNKNOWN/LLM-HOLD/watchdog/halt/health-endpoint/config gates).
- Docs: `docs/phases/phase-12.md`, `docs/operations/hardening.md` runbook.

## [0.12.0] - 2026-09-23

### Added
- Phase 11: read-only web dashboard (stdlib only, no actions).
- Dashboard: section models + `to_dict()`, `DashboardStateProvider`
  (best-effort sections, day-P&L, session state), static LLM cost estimator,
  GET-only `DashboardApp` (`/`, `/api/state`, `/health`; 405/404/400 JSON).
- Settings: `dashboard_host/port/refresh_s`.
- Scripts: `scripts/serve_dashboard.py` (graceful Ctrl+C).
- Tests: provider/cost/HTTP-contract suites (ephemeral port).
- Docs: `docs/phases/phase-11.md`, `docs/operations/dashboard.md`.

## [0.11.0] - 2026-09-23

### Added
- Phase 10: agent orchestrator running the full 9-stage lifecycle.
- Domain: `Stage/StageStatus/StageOutcome/AgentCycle`.
- Application: `Observer`, `ContextBuilder`, `TradingAgent`
  (`run_cycle` never raises; looping `run` + `stop()` for graceful shutdown;
  per-stage memory writes; planner-optional HOLD degradation).
- Settings: `agent_symbols/interval/candle_count`.
- Scripts: `scripts/run_agent.py` (one-shot, `--loop`, SIGINT/SIGTERM).
- Tests: fake-port cycle/loop/shutdown suites + gated live dry-run cycle.
- Docs: `docs/phases/phase-10.md`, `docs/operations/agent.md`.

## [0.10.0] - 2026-09-23

### Added
- Phase 09: SQLite-backed memory with four scoped facades.
- Domain: `MemoryScope/MemoryKind/MemoryRecord` (280-char summaries).
- Memory: `MemoryStore` ABC, thread-safe `SQLiteMemoryStore` (WAL,
  `:memory:` for tests), `ShortTerm/Trade/World/StrategyMemory` with
  retention pruning + whitelisted compact writers.
- Settings: `memory_db_path` + per-scope keeps.
- Scripts: `scripts/check_memory.py` (inspect + `--demo`).
- Tests: store (filters/prune/persistence) + facade suites.
- Docs: `docs/phases/phase-09.md`, expanded `docs/memory/design.md`.

## [0.9.0] - 2026-09-23

### Added
- Phase 08: execution engine for approved decisions (no direct proposals).
- Domain: `ExecutionMode/OrderRequest/ExecutionStatus/ExecutionRecord`;
  `AccountInfo.trade_mode`.
- Execution: `TradeExecutor` ABC + `MT5TradeExecutor`
  (validate→prepare→order_check→execute→verify→record, idempotency ledger,
  DRY_RUN default, DEMO-vs-REAL guard, LIVE dual gate).
- Settings: `execution_*` block + live-requires-opt-in validation.
- Scripts: `scripts/check_execute.py` (dry_run default, demo explicit).
- Tests: execution-model + full lifecycle suites (fakes).
- Docs: `docs/phases/phase-08.md`, `docs/operations/execution.md`.

## [0.8.0] - 2026-09-23

### Added
- Phase 07: Supervisor + deterministic risk engine (safety boundary).
- Risk: 13 `ViolationCode`s, `ValidationResult`, `RiskConfig`/`TradingSession`,
  `RiskContext`/`DecisionRecord`, 13 one-concern `RiskRule`s, `RiskEngine`,
  `Supervisor` (pure `check()` + recording `review()` with ledger).
- Rules: max risk/daily-loss/positions/exposure, allowlist, UTC sessions,
  spread cap, mandatory SL/TP, min stop distance, duplicates, cooldowns,
  account safety. Rejection over correction; abstention documented.
- Settings: `risk_*` block + `to_risk_config()` (symbols/sessions parsing).
- Scripts: `scripts/check_risk.py` live-state probe (never executes).
- Tests: per-rule boundaries + supervisor ledger suites + settings parsing.
- Docs: `docs/phases/phase-07.md`, expanded `docs/risk/rules.md`.

## [0.7.0] - 2026-09-23

### Added
- Phase 06: LLM planner producing validated trade proposals (no execution).
- Domain: `TradeAction/PlannerInput/MemoryNote/TradeProposal` (+ audit metadata).
- AI: `Planner` ABC, `LLMPlanner` (JSON contract, strict validation,
  HOLD fallback), prompt builder, `hold_proposal`.
- Scripts: `scripts/check_plan.py` (`--stub` offline + live LLM).
- Tests: planning-model + planner suites (fake providers, no-execution check).
- Docs: `docs/phases/phase-06.md`, `docs/ai/planner.md`.

## [0.6.0] - 2026-09-23

### Added
- Phase 05: provider-agnostic LLM layer (no trading use).
- AI: `LLMMessage/LLMRequest/LLMResponse/LLMUsage`, `LLMProvider` ABC,
  typed errors, stdlib `HttpClient` transport.
- Adapters: `OpenAICompatibleProvider` (openai/deepseek/ollama presets) +
  `GeminiProvider`; structured JSON output; latency + token tracking.
- Factory: `create_provider()/provider_from_settings()` (`none` default).
- Settings: `llm_api_key/llm_base_url` (env-only key, masked redaction).
- Scripts: `scripts/check_llm.py` probe.
- Tests: model/adapter suites (fake transports) + gated live test.
- Docs: `docs/phases/phase-05.md`, expanded `docs/ai/providers.md`.

## [0.5.0] - 2026-09-23

### Added
- Phase 04: deterministic strategy engine (LLM-free).
- Domain: `Direction/DecisionAction/Setup/MarketContext(=StrategyContext)/
  StrategySignal/StrategyDecision`.
- Strategies: `Strategy` ABC, observation-only `NullStrategy`,
  extensible `MeasureMoveStrategy` + concrete `DonchianBreakoutStrategy`
  (validated `MeasureMoveParams`, confirm/confidence/setup hooks).
- Application: `StrategyService` fan-out + `triage` (CANDIDATE/OBSERVE/SKIP,
  per-strategy failure containment).
- Scripts: `scripts/check_strategy.py` live-signal probe.
- Tests: model/synthetic-breakout/service suites + gated live test.
- Docs: `docs/phases/phase-04.md`, expanded `docs/strategy/engine.md`.

## [0.4.0] - 2026-09-23

### Added
- Phase 03: read-only account/orders/positions/history (no execution).
- Domain: `Position/Order/Deal/TradeResult/AccountState/PositionSide` +
  `PositionPort/OrderPort/HistoryPort`.
- Infrastructure: `MT5TradingDataAdapter` (`positions_get/orders_get/
  history_deals_get/history_orders_get`), trading mappers.
- Application: `AccountService/PositionService/OrderService/HistoryService`
  (exposure/net/floating, realized P&L, closed-trade grouping).
- Scripts: `scripts/check_trading.py` state probe.
- Tests: trading model/mapper/adapter suites + gated live state test.
- Docs: `docs/phases/phase-03.md`, `docs/mt5/trading-state.md`.

## [0.3.0] - 2026-09-23

### Added
- Phase 02: read-only market-data layer (no trading).
- Domain: `Tick/Candle/SymbolInfo/MarketSnapshot/Timeframe` + `MarketDataPort`;
  `MT5MarketDataError`, `MT5SymbolNotFoundError`.
- Infrastructure: `MT5MarketDataAdapter` (`copy_rates_from_pos/symbol_info_tick/
  symbol_info`), market mappers (namedtuple/mapping/numpy rows -> domain, UTC),
  timeframe resolution.
- Application: `MarketService` (symbol/count validation, snapshot convenience).
- Settings: `mt5_default_symbol/timeframe/candles`.
- Scripts: `scripts/check_market.py` snapshot probe.
- Tests: model/mapper/adapter-service suites + gated live snapshot test.
- Docs: `docs/phases/phase-02.md`, `docs/mt5/market-data.md`.

## [0.2.0] - 2026-09-23

### Added
- Phase 01: read-only MT5 connectivity (no trading).
- Domain: `AccountInfo`, `TerminalInfo`, `MT5Credentials` (masked),
  `ConnectionConfig`, `ConnectionHealth`, `MT5ConnectionPort`, typed errors.
- Infrastructure: guarded `load_mt5()`, MT5->domain mappers,
  thread-safe `MT5ConnectionAdapter` (injectable module double).
- Application: `ConnectionService` + `RetryPolicy`
  (ensure_connected/reconnect, fail-safe health).
- Settings: `MT5_AGENT_MT5_PATH` + `to_connection_config()`.
- Scripts: `scripts/check_mt5.py` read-only probe.
- Tests: mapper/adapter/service unit suites; gated live-terminal integration test.
- Docs: `docs/phases/phase-01.md`, expanded `docs/mt5/integration.md`.

## [0.1.0] - 2026-09-23

### Added
- Phase 00: project foundation (no trading functionality).
- Typed `mt5_agent` package with layered placeholders
  (domain/application/infrastructure/strategies/ai/risk/execution/memory/dashboard).
- YAML + env-var configuration (`MT5_AGENT_*`) with demo-first validation
  (`dry_run` default; `live` requires explicit opt-in).
- Structured JSON/text logging (`logging_utils`).
- CLI entry-point (`python -m mt5_agent`, `mt5-agent`).
- Tooling: Ruff, MyPy (strict), Pytest, pre-commit, GitHub Actions CI.
- Docs framework + `docs/phases/phase-00.md`; root docs
  (README/ROADMAP/CHANGELOG/CONTRIBUTING/SECURITY/LICENSE).
