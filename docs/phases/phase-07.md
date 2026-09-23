# Phase 07 — Supervisor and Risk Engine

## Objective
Enforce the critical safety boundary: every LLM `TradeProposal` passes
deterministic validation before anything can execute. The Supervisor can
reject anything; the LLM can override nothing. Rejection beats silent
correction — proposals are never modified, only approved or rejected with
explicit codes.

## Scope
In scope: `ViolationCode/ValidationResult/RiskConfig/RiskContext` models,
13 `RiskRule`s, `RiskEngine`, `Supervisor` (+ ledger), settings wiring,
unit tests per rule, `scripts/check_risk.py` live probe.
Out of scope: execution (Phase 08), memory persistence (Phase 09).

## Architecture
```
risk/
  result.py      # ViolationCode (13 stable codes), Violation, ValidationResult
  config.py      # RiskConfig (all limits) + TradingSession (UTC windows)
  context.py     # RiskContext (account/positions/orders/spreads/points/time/
                 # day_pnl/decision history) + DecisionRecord
  rules.py       # RiskRule ABC + 13 one-concern rules + DEFAULT_RULES
  engine.py      # RiskEngine.validate() (HOLD fast-path, else all-rules)
  supervisor.py  # Supervisor.check() pure + review() recording ledger
```
Rules read `(proposal, context, config)` and return `Violation | None`.
Engine aggregates; Supervisor enriches context with its ledger and records
non-HOLD verdicts. No rule ever mutates a proposal.

## Components
- Codes: `MAX_RISK_EXCEEDED, MAX_DAILY_LOSS_EXCEEDED, MAX_POSITIONS_EXCEEDED,
  MAX_EXPOSURE_EXCEEDED, SYMBOL_NOT_ALLOWED, SESSION_CLOSED, SPREAD_TOO_HIGH,
  STOP_LOSS_REQUIRED, TAKE_PROFIT_REQUIRED, STOP_TOO_CLOSE, DUPLICATE_TRADE,
  COOLDOWN_ACTIVE, ACCOUNT_UNSAFE`.
- Rules: max risk/trade, daily loss (abstains when `day_pnl` unknown),
  max positions, max exposure (current + proposed volume), symbol allowlist
  (open when `None`), UTC sessions (overnight spans supported), spread cap
  (abstains when unknown), mandatory SL/TP, min stop distance in points
  (abstains when point size unknown), duplicate (open same-side position or
  recent same-side approval), per-symbol cooldown, account safety
  (trade flag, positive equity, margin-level floor).
- `ValidationResult(approved, violations, checked_at)` with invariants
  (approved <=> no violations); `SupervisorDecision` audit record.

## Interfaces
- `RiskEngine.validate(proposal, context, *, now?) -> ValidationResult`
- `Supervisor.check(proposal, context, *, now?) -> ValidationResult` (pure)
- `Supervisor.review(proposal, context, *, now?) -> SupervisorDecision`
  (records non-HOLD verdicts to the ledger)

## Data Models
See Components. `RiskConfig` defaults are conservative demo-first
(1%/trade, 3%/day, 3 positions, 1.0 lots exposure, SL+TP mandatory).

## Configuration
- `config/app.yaml`: full `risk_*` block; env `MT5_AGENT_RISK_*` overrides.
- `risk_allowed_symbols`: comma list or null (open); `risk_allowed_sessions`:
  `"0-24"` or `"8-18,20-23"`; spread cap null = disabled; windows 0 = disabled.
- Probe: `check_risk.py --symbol EURUSD --action BUY --entry … --stop-loss …
  --take-profit … [--risk-pct … --volume …]` (HOLD default).

## Error Handling
Config errors (bad sessions, non-positive limits) raise at startup.
Evaluation never raises for market conditions — violations are data.
Unknown spread/point/P&L makes the affected rule abstain (documented above),
never block: availability of data, not absence of risk, gates those rules.

## Security Considerations
This is THE boundary: LLM output cannot reach execution except through
`Supervisor.review() == approved`. Rejection is explicit and auditable
(codes + messages + timestamps). The ledger is process-local in Phase 07;
Phase 09 persists verdicts.

## Testing Strategy
- `test_risk_rules`: pass/fail boundary per rule (incl. overnight sessions,
  abstentions, multi-violation aggregation, result invariants).
- `test_supervisor`: check purity, review recording, duplicate + cooldown via
  injected `now`, HOLD exclusion, audit fields.
- Settings: defaults, symbol/session parsing, spec validation.

## Acceptance Criteria
- [x] `Supervisor/RiskEngine/RiskRule/ValidationResult` exist
- [x] All 13 deterministic rules implemented with explicit codes
- [x] Rejection preferred over correction (no mutation paths)
- [x] `MAX_RISK_EXCEEDED` et al returned as data, never silent

## Definition of Done
Boxes checked; `pytest/ruff/mypy` green; live probe verified; diff reviewed;
focused commit `feat(phase-07): ...` pushed.

## Files Added
- `src/mt5_agent/risk/{result,config,context,rules,engine,supervisor}.py`
- `tests/unit/{test_risk_rules,test_supervisor}.py`
- `scripts/check_risk.py`

## Files Modified
- `src/mt5_agent/risk/__init__.py`
- `src/mt5_agent/config/settings.py` (`risk_*` + `to_risk_config`)
- `config/app.yaml`, `.env.example`, `tests/unit/test_settings.py`
- `docs/risk/rules.md`, `README.md`, `ROADMAP.md`, `CHANGELOG.md`,
  `pyproject.toml` (v0.8.0)

## Dependencies
None new.

## Future Work
Phase 08: execution engine (`validate -> prepare -> order_check -> execute ->
verify -> record`, DRY_RUN/DEMO only) consuming only approved proposals.
