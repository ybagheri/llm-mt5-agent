# Development

## Local workflow

1. Create or activate `.venv`.
2. Install `-e ".[dev,mt5]"` on Windows.
3. Run the non-integration tests, Ruff, and MyPy.
4. Use injected fakes for normal development.
5. Use the read-only MT5 probes against the Demo terminal.
6. Use dry-run before any Demo execution test.
7. Review the diff and secret scan before each commit.

## Conventions

- Keep domain models pure and typed.
- Keep MT5 calls inside infrastructure adapters.
- Keep strategy calculations deterministic and separate from LLM code.
- Add a regression test for every safety or mapping change.
- Keep defaults conservative and explicit.
- Do not log credentials, API keys, passwords, or account identifiers.

## Quality commands

```powershell
pytest -m "not integration" -q
ruff check src tests scripts
ruff format --check src tests scripts
mypy src
pre-commit run --all-files
```

`pip-audit` and wheel installation are additional release checks. Live MT5 tests are intentionally gated and should be run only in a controlled Demo environment.
