# Contributing

## Workflow (per phase)
1. Inspect: `git status`, `git log --oneline -10`, `git diff`.
2. Read relevant `docs/phases/phase-XX.md`.
3. Plan small, incremental changes (SOLID, clean architecture).
4. Implement: domain has no MT5/HTTP/DB/LLM deps; adapters live in infrastructure.
5. Verify: `pytest -m "not integration" -q`, `ruff check src tests`, `mypy src`.
6. Update docs + ROADMAP + CHANGELOG.
7. Focused commit: `feat(phase-XX): ...` (one phase per commit).

## Rules
- Demo-first; never enable live trading by default.
- No secrets in code, config files, logs, or commits (`.env` is git-ignored).
- LLM never executes; Supervisor validation is deterministic.
- Mock MT5/LLM/network in unit tests; mark live-terminal tests `integration`.
- Keep functions/classes small; prefer composition + dependency injection.
