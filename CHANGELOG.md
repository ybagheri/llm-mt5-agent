# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
