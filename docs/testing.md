# Testing

## Local quality suite

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,mt5]"
pytest -m "not integration" -q
ruff check src tests scripts
ruff format --check src tests scripts
mypy src
```

The unit suite uses fake ports and providers. It must not require MT5, network access, credentials, or orders.

## MT5 integration

MT5 tests are gated by `MT5_AGENT_RUN_LIVE_MT5_TESTS=true`:

```powershell
$env:MT5_AGENT_RUN_LIVE_MT5_TESTS = 'true'
pytest tests/integration -q
```

The verified environment produced successful read-only terminal and `EURUSD M1` market checks. A terminal with Algo Trading disabled cannot validate Demo order submission; report that as blocked rather than claiming success.

## Test categories

- unit: models, mappers, strategies, planner, risk, execution gates, memory, dashboard, logging;
- fake integration: connection, market, trading, and agent flows with injected doubles;
- gated MT5: terminal, account, symbol, candle, and history reads;
- manual paper: snapshot, analysis, planner, risk, journal, and dry-run execution;
- demo execution: only with explicit operator intent and a verified Demo account.

A passing software test does not demonstrate profitability or a high win rate.
