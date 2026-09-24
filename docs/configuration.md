# Configuration

Configuration is read from `config/app.yaml`, then overridden by `MT5_AGENT_*` environment variables and `.env`. An explicitly selected configuration path that does not exist is an error.

## Safe defaults

```yaml
trading_mode: dry_run
enable_live_trading: false
execution_mode: dry_run
risk_require_stop_loss: true
risk_require_take_profit: true
```

`trading_mode` and `execution_mode` must match. `execution_mode` is the actual mode used by the executor and displayed by the dashboard.

## MT5

Set `MT5_AGENT_MT5_PATH` for the executable, and provide login/password/server through environment variables when the terminal is not already logged in. The adapter dynamically reads symbol point size, volume limits, digits, and trade mode; no broker-specific volume assumptions should be added to strategy code.

## LLM

Set `MT5_AGENT_LLM_PROVIDER`, model, base URL, timeout, and API key. `none` produces a HOLD-only planner. OpenAI-compatible providers can use a local Ollama or LM Studio endpoint. Do not send account data to a hosted provider until its retention and training policy is understood.

## Risk

Risk settings are deterministic and are never supplied by the LLM. Configure maximum risk, daily loss, account-wide position count, gross exposure, symbols, sessions, spread, stop distance, duplicate window, cooldown, and margin floor.

Unknown daily P&L, spread, or symbol point data rejects a directional proposal. This is deliberate fail-closed behavior.

## Journal and dashboard

`MT5_AGENT_MEMORY_DB_PATH` points to the local SQLite journal. The dashboard defaults to `127.0.0.1`; it is read-only and unauthenticated. Do not bind it publicly without an authenticated TLS reverse proxy.
