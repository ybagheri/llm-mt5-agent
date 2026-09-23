# Phase 00 — Project Foundation

## Objective
Establish a clean, typed, tested, demo-first Python foundation with configuration,
structured logging, tooling, CI, and documentation — no trading functionality.

## Scope
In scope: packaging, layered package skeleton, settings, logging, CLI smoke,
Ruff/MyPy/Pytest/pre-commit/CI, root + docs framework.
Out of scope: any MT5/strategy/LLM/risk/execution/memory/agent/dashboard logic.

## Architecture
`src/` layout (`mt5_agent` package); `domain/` has zero external deps by
convention; `config/` + `logging_utils` are the only functional modules.
Precedence: kwargs → env (`MT5_AGENT_*`) → YAML → safe defaults.

## Components
- `config/settings.py` (`AppSettings`, demo-first validator)
- `config/loader.py` (YAML + `.env` + env resolution)
- `logging_utils.py` (JSON/text formatters, `configure_logging`, `get_logger`)
- `__main__.py` (argparse CLI: `--version/--config/--log-level/--log-format`)
- Layer placeholders: domain/application/infrastructure/strategies/ai/risk/execution/memory/dashboard

## Interfaces
- `load_settings(config_path=None, load_env_file=True) -> AppSettings`
- `AppSettings.from_mapping(dict)`, `AppSettings.masked()`, `AppSettings.default_config_path()`
- `configure_logging(level, log_format, stream, force)`, `get_logger(name)`

## Data Models
`AppSettings`: `app_name/env/log_level/log_format/trading_mode/enable_live_trading/`
`mt5_login/mt5_server/mt5_timeout_ms/mt5_portable/llm_provider/llm_model/llm_timeout_s`.

## Configuration
`config/app.yaml` (defaults) + `.env.example`; `MT5_AGENT_*` overrides file.
`trading_mode=dry_run`, `enable_live_trading=false`; `live` without opt-in → `ValueError`.

## Error Handling
Missing config file → defaults; invalid YAML / non-mapping → `ValueError`;
invalid settings → Pydantic `ValidationError`; logging never raises.

## Security Considerations
No secrets in repo (`.env` ignored, `.env.example` empty);
live blocked by default; `masked()` hook for future secret-bearing fields;
pre-commit `detect-private-key`; CI has no secret handling yet (Phase 12).

## Testing Strategy
Unit (`tests/unit`): package version, settings defaults/validation/env-over-file/
bad-YAML, logging smoke. Integration (`tests/integration`, marked `integration`,
skipped in CI): placeholder only. No MT5 terminal required.

## Acceptance Criteria
- [x] `pip install -e ".[dev]"` succeeds (Python 3.12+)
- [x] `pytest -m "not integration"` passes
- [x] `ruff check` + `ruff format --check` pass
- [x] `mypy src` (strict) passes
- [x] `.github/workflows/ci.yml` present and valid
- [x] README/ROADMAP/CHANGELOG/CONTRIBUTING/SECURITY/LICENSE + docs framework exist
- [x] No secrets committed (`.env.example` contains no values)

## Definition of Done
All acceptance boxes checked; diff reviewed; focused commit `feat(phase-00): ...`.

## Files Added
- `pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`
- `.gitignore`, `.env.example`, `config/app.yaml`
- `src/mt5_agent/{__init__,__main__,logging_utils,py.typed,config/{__init__,settings,loader},domain,application,infrastructure,strategies,ai,risk,execution,memory,dashboard/__init__}`
- `tests/{conftest,unit/{test_package,test_settings,test_logging},integration/test_placeholder}`
- `scripts/smoke.py`
- `README.md`, `ROADMAP.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`
- `docs/{README,architecture/overview,development/setup,mt5/integration,ai/providers,strategy/engine,risk/rules,memory/design,operations/configuration,phases/phase-00..12}`

## Files Modified
None (greenfield; `E:\llm-mt5-agent` was empty).

## Dependencies
Runtime: `pyyaml`, `pydantic`, `pydantic-settings`, `python-dotenv`.
Dev: `pytest`, `ruff`, `mypy`, `pre-commit`, `types-PyYAML`.
Optional (unused yet): `MetaTrader5; sys_platform=='win32'`.

## Future Work
Phase 01: MT5 connectivity abstraction (terminal/account/health/reconnect) behind
domain interfaces; read-only; trading stays disabled.
