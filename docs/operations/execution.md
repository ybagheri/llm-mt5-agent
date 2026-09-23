# Execution (Phase 08)

Approved decisions only. The executor takes `SupervisorDecision` — raw
proposals, rejected verdicts, and HOLDs become REJECTED records without
touching the terminal.

## Modes
| Mode | Behavior |
|---|---|
| `DRY_RUN` (default) | Simulated SUCCESS, zero terminal calls |
| `DEMO` | Real `order_check`/`order_send`; refused on `trade_mode == REAL` accounts |
| `LIVE` | Requires `allow_live=True` **and** `MT5_AGENT_ENABLE_LIVE_TRADING=true` |

`execution_mode` + `execution_default_volume/magic/deviation` live in
`config/app.yaml` (`MT5_AGENT_EXECUTION_*` overrides).

## Lifecycle
`validate → prepare → order_check → execute → verify → record`, audited as
`ExecutionRecord` (ticket/deal/prices/slippage/error/status). Retries reuse
`client_id`: completed attempts replay from the ledger, so duplicates are
impossible by retry.

## Probe
```powershell
python scripts/check_execute.py --mode dry_run            # safe default
python scripts/check_execute.py --mode demo --client-id x # real demo order!
```
The probe builds a fixed tiny intent from the live signal (HOLD when flat),
runs Supervisor first, then executes. No LIVE option exists in the script.
