# Strategy engine

Deterministic, LLM-free market-facts layer. Strategies read `MarketContext`
(Phase 02 snapshot + optional Phase 03 account state) and emit `StrategySignal`.

## Quick probe
```powershell
python scripts/check_strategy.py --symbol EURUSD --timeframe M1 --count 50 --lookback 20
```
Prints per-strategy direction/confidence/setups/facts plus triage decisions.

## Strategies
- `NullStrategy` — observation-only baseline, always `FLAT`.
- `MeasureMoveStrategy` — impulse/structure-break pipeline with overridable
  hooks (`confirm`, `confidence_of`, `setup_for`) and validated
  `MeasureMoveParams(lookback, min_candles, breakout_confidence)`.
- `DonchianBreakoutStrategy` — concrete N-bar close-break reader:
  close above prior high -> `LONG`, below prior low -> `SHORT`, else `FLAT`
  with explicit `skip` facts (short data / no break / vetoed).

## Service
`StrategyService([NullStrategy(), DonchianBreakoutStrategy()])` fans out
`analyze()` (failures degrade to FLAT error signals) and `decide()` triages:
directional -> `CANDIDATE`, flat-with-setups -> `OBSERVE`, else `SKIP`.
Later phases feed these signals to the Planner (LLM) and Supervisor.
