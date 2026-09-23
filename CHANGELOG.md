# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
