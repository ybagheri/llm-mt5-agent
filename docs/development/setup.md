# Development setup

Requires Python 3.12+.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pre-commit install
pytest -m "not integration" -q
ruff check src tests
ruff format --check src tests
mypy src
python -m mt5_agent --help
```

Conventions: typed code, small modules, `MT5_AGENT_*` env vars, JSON logs,
unit tests mock all external services.
