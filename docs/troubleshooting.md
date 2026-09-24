# Troubleshooting

## MT5 not found

Set `MT5_AGENT_MT5_PATH` to the terminal executable and verify the file exists. Do not use the data directory as the executable path.

## Terminal is not ready

Launch MT5, wait for the connection indicator, and confirm the account/server. Run `python scripts/check_mt5.py` before market probes.

## Python cannot connect

Confirm the terminal is running, the package was installed in `.venv`, and `MetaTrader5` imports. The official Python MT5 package is Windows-only and requires a 64-bit Python installation compatible with the terminal.

## Symbol unavailable

Use a symbol name discovered from the broker terminal. Check Market Watch visibility, symbol trading mode, and server data availability.

## No candles or market closed

The terminal may have no bars for the requested timeframe or session. Check `scripts/check_market.py` output and try a liquid symbol/timeframe only after confirming broker availability.

## LLM timeout or invalid JSON

Check provider, model, base URL, timeout, connectivity, and API-key environment configuration. The safe result is `HOLD`; inspect scrubbed logs without printing secrets.

## Order rejected

Inspect MT5 error details, symbol point/volume constraints, spread, stop distance, margin, market mode, and Algo Trading state. The executor never retries an `UNKNOWN` timeout blindly.

## Permission or path errors

Use absolute Windows paths where needed, verify parent directories, and ensure the virtual environment has permission to write the configured SQLite path and data directory.

## Dashboard exposure

Keep the dashboard on `127.0.0.1`. It is unauthenticated and intended to be read-only. Put it behind authenticated TLS if remote access is required.

## Virtual environment problems

Recreate `.venv` only after confirming it contains no local work:

```powershell
Remove-Item -Recurse -Force .venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,mt5]"
```
