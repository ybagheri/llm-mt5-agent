# Security

## Non-negotiables
1. Demo-first; dry-run-first; no live trading by default.
2. LLM cannot bypass Supervisor; risk limits are deterministic code, not prompts.
3. Secrets (passwords, API keys, account numbers) live in environment/`.env` only.
   Never in git, YAML, logs, or issues. `.env` is git-ignored.
4. Every trade proposal and execution attempt must be auditable with a reason.
5. External failures (MT5/LLM) must fail safely (reject/halt, never trade blind).

## Reporting
Report suspected vulnerabilities privately to the maintainers. Do not open public
issues with secrets, account numbers, or broker details. Rotate any exposed credential
immediately.

## Hardening (Phase 12)
Audit logs, health checks, watchdog, retry/reconnect policies, timeouts,
idempotent execution, secret management review, and deployment guidance.
Live trading remains disabled unless explicitly enabled after review.
