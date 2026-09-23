# Dashboard operations (Phase 11)

Read-only web view (stdlib `http.server`, no dependencies). No trading
actions exist — mutating HTTP verbs return 405.

## Serve
```powershell
python scripts/serve_dashboard.py
python scripts/serve_dashboard.py --port 8090
```
Open the printed URL (default `http://127.0.0.1:8080`). `?symbol=XAUUSD` and
`?timeframe=H1` query params select the market section; the page refreshes
every `dashboard_refresh_s` (default 15s).

## Endpoints
- `GET /` — single HTML page (account/market/agent/risk/LLM/memory tables).
- `GET /api/state?symbol=EURUSD&timeframe=M1` — full JSON state.
- `GET /health` — `{"ok": true}`.

## Notes
Binds loopback by default; keep it that way until the Phase 12 security
review. Day P&L needs history access, otherwise `null`. LLM usage/cost
appears after `record_llm()` receives a call (wired by future orchestrator
work); unknown models show cost `null` rather than a guess.
