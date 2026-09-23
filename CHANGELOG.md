# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
