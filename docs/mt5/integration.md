# MT5 integration

The official `MetaTrader5` Python package is a Windows-only adapter around the
MT5 terminal (verified: `pip show MetaTrader5 == 5.0.6180`; API surface:
`initialize/login/shutdown/version/last_error/account_info/terminal_info/...`
per https://www.mql5.com/en/docs/python_metatrader5).

## Layering rules (enforced from Phase 01)
- `domain/` never imports `MetaTrader5` (models: `AccountInfo`, `TerminalInfo`,
  `ConnectionConfig`, `ConnectionHealth`, `MT5Credentials`; port:
  `MT5ConnectionPort`; errors in `domain/errors.py`).
- `application/` orchestrates via the port only (`ConnectionService` +
  `RetryPolicy`: `ensure_connected` with retries, `reconnect`, fail-safe
  `check_health`). No direct MT5 calls.
- `infrastructure/mt5/` is the only MT5-touching code:
  `module.load_mt5()` (Windows/install guard), `mappers` (namedtuple -> domain),
  `connection_adapter.MT5ConnectionAdapter` (injectable module double for tests).

## Usage (read-only)
```powershell
copy .env.example .env   # fill MT5_AGENT_MT5_* (password via env only)
python scripts/check_mt5.py
```
With explicit path (e.g. Alpari terminal):
```powershell
$env:MT5_AGENT_MT5_PATH="C:\Users\bagheri\AppData\Roaming\Alpari MT5\terminal64.exe"
python scripts/check_mt5.py
```
Exit 0 + JSON on success; exit 1 + `{"connected": false, ...}` on failure.
Never sends orders — no execution code exists yet.

## Failure modes
| Symptom | Meaning |
|---|---|
| `MT5NotAvailableError` | non-Windows or package missing (`pip install MetaTrader5`) |
| `MT5ConnectionError` | `initialize()` false (see `last_error()` in message) |
| `MT5LoginError` | `login()` false (login/server shown, password never logged) |
| `MT5NotConnectedError` | read before `connect()` |
| `MT5DataError` | `account_info()/terminal_info()` returned `None`/garbage |

## Testing
Unit tests use `FakeMT5` doubles — no terminal required. Live probe:
```powershell
$env:MT5_AGENT_RUN_LIVE_MT5_TESTS="true"
pytest tests/integration/test_mt5_live.py -q
```
Skips cleanly when the terminal is unavailable. CI always runs
`pytest -m "not integration"`.
