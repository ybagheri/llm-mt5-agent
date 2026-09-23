# Architecture overview

Layered, clean architecture (Phase 00 placeholder):

```
src/mt5_agent/
  domain/          # pure models + interfaces (no MT5/HTTP/DB/LLM deps)
  application/     # orchestration services
  infrastructure/  # MT5/DB/HTTP adapters (Phase 01+)
  strategies/      # deterministic strategy engine (Phase 04+)
  ai/              # LLM provider adapters (Phase 05+)
  risk/            # supervisor + risk rules (Phase 07+)
  execution/       # trade executor (Phase 08+)
  memory/          # memory stores (Phase 09+)
  dashboard/       # read-only web state (Phase 11+)
  config/          # YAML + env-var settings (Phase 00 ✅)
```

Enforced flow: `LLM → TradeProposal → Supervisor → Executor → MT5`.
Application services compose domain components via dependency injection.
