# Configuration

Sources (highest precedence first): constructor kwargs → `MT5_AGENT_*` env vars
(`.env` supported) → YAML file (`--config` / `MT5_AGENT_CONFIG` / `config/app.yaml`)
→ safe defaults.

- Non-secret defaults: `config/app.yaml`.
- Secrets/templates: `.env.example` → local `.env` (git-ignored).
- Demo-first: `trading_mode` defaults to `dry_run`; `live` requires
  `MT5_AGENT_ENABLE_LIVE_TRADING=true` or validation fails.
- Never log secrets; use `AppSettings.masked()` patterns for diagnostics.
