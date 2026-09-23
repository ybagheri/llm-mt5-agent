# llm-mt5-agent

AI-assisted MetaTrader 5 agent — **demo-first, supervised, auditable**.

```
OBSERVE → CONTEXT → STRATEGY → MEMORY → PLAN → SUPERVISE → EXECUTE → VERIFY → MEMORY UPDATE
```

## Safety model

- LLM is a **planner only**: `LLM → TradeProposal → Supervisor → Executor → MT5`.
- Supervisor can **reject** any proposal; LLM can never override risk limits.
- **Demo-first**: default `trading_mode=dry_run`, live trading requires explicit opt-in.
- Every proposal and execution is auditable; failed validation returns a reason.

See [docs/architecture/overview.md](docs/architecture/overview.md) and [SECURITY.md](SECURITY.md).

## Current status

**Phase 01 — MT5 Connectivity** (read-only; no trading functionality).

- ✅ Typed Python package (`src/mt5_agent`)
- ✅ YAML + env-var configuration with safe defaults
- ✅ Structured (JSON) logging
- ✅ Ruff / MyPy / Pytest / pre-commit / GitHub Actions CI
- ✅ MT5 connection layer (`MT5ConnectionPort` + adapter + `ConnectionService`);
  terminal/account snapshots, health checks, reconnect (`scripts/check_mt5.py`)

Roadmap: [ROADMAP.md](ROADMAP.md) · Changes: [CHANGELOG.md](CHANGELOG.md) · Phases: [docs/phases/](docs/phases/)

## Quick start

Requires Python 3.12+ (Windows required from Phase 01 for MT5).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
python -m mt5_agent --help
python scripts/smoke.py
python scripts/check_mt5.py  # read-only MT5 probe (needs terminal on Windows)
pytest -m "not integration" -q
ruff check src tests scripts
mypy src
```

## Configuration

- `config/app.yaml` — non-secret defaults.
- `.env` / environment (`MT5_AGENT_*`) — overrides + secrets (never commit).
- See [.env.example](.env.example) and [docs/operations/configuration.md](docs/operations/configuration.md).

## Development / testing / docs

- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Docs index: [docs/README.md](docs/README.md)
- Phase docs: [docs/phases/phase-00.md](docs/phases/phase-00.md)

## Roadmap (abridged)

Foundation → MT5 read-only → Market data → Account → Strategy → LLM → Planner → Supervisor → Demo exec → Memory → Agent → Dashboard → Hardening.

## Disclaimer

Educational software. Trading involves substantial risk. No live trading by default; use demo/dry-run. Not financial advice. See [SECURITY.md](SECURITY.md) and [LICENSE](LICENSE).
