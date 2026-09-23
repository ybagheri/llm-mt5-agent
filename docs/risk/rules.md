# Risk rules

Deterministic Supervisor boundary (Phase 07). The LLM proposes; these rules
dispose — approve only when every rule passes. Proposals are never edited,
only rejected with explicit codes.

## Rules & codes
| Code | Gate |
|---|---|
| `MAX_RISK_EXCEEDED` | `risk_pct` <= `risk_max_risk_pct` (default 1.0) |
| `MAX_DAILY_LOSS_EXCEEDED` | day P&L within `risk_max_daily_loss_pct` (default 3.0; abstains if unknown) |
| `MAX_POSITIONS_EXCEEDED` | open positions < `risk_max_positions` (default 3) |
| `MAX_EXPOSURE_EXCEEDED` | current + proposed volume <= `risk_max_exposure` (default 1.0) |
| `SYMBOL_NOT_ALLOWED` | allowlist (`risk_allowed_symbols`, null = open) |
| `SESSION_CLOSED` | UTC hour inside `risk_allowed_sessions` (default `0-24`) |
| `SPREAD_TOO_HIGH` | spread <= `risk_max_spread_points` (null = off; abstains if unknown) |
| `STOP_LOSS_REQUIRED` / `TAKE_PROFIT_REQUIRED` | mandatory brackets (both default on) |
| `STOP_TOO_CLOSE` | stop distance >= `risk_min_stop_points` (0 = off; needs point size) |
| `DUPLICATE_TRADE` | no open same-side position + no same-side approval in window (default 600s) |
| `COOLDOWN_ACTIVE` | per-symbol quiet period (default 60s, 0 = off) |
| `ACCOUNT_UNSAFE` | trade flag on, equity > 0, margin level >= floor (default 100%) |

`HOLD` proposals always pass (no-op). Configure via `config/app.yaml`
(`risk_*`) or `MT5_AGENT_RISK_*` env vars.

## Probe
```powershell
python scripts/check_risk.py --symbol EURUSD --action HOLD
python scripts/check_risk.py --symbol EURUSD --action BUY --entry 1.1 `
  --stop-loss 1.09 --take-profit 1.12 --risk-pct 0.5 --volume 0.01
```
Prints `approved`, violation codes/messages, and account context. Never executes.
