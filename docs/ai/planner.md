# Planner (Phase 06)

The Planner turns structured context into exactly one validated
`TradeProposal`. It advises; it never executes (source-tested invariant).

## Input
`PlannerInput`: symbol/timeframe, `MarketSnapshot`, `StrategySignal`,
optional `AccountState`, open `Position`s, and `MemoryNote`s (minimal
kind/text excerpts until the Phase 09 store lands).

## LLMPlanner
Wraps any Phase 05 provider: fixed JSON-only system contract + deterministic
user JSON (20 candles, tick, signal facts, account, positions, memory) ->
`response_format='json'` -> strict `validate_proposal()`:
symbol comes from input (never the LLM), BUY needs `SL<entry<TP>`, SELL needs
`TP<entry<SL`, rationale/confidence/risk ranges enforced. Any failure ->
`HOLD` with the cause recorded. Audit metadata (provider/model/latency) is
attached to every proposal.

## Probe
```powershell
python scripts/check_plan.py --stub                                    # offline
python scripts/check_plan.py --symbol EURUSD --timeframe M1 --count 50  # live LLM
```
Next: Phase 07 Supervisor validates every proposal against deterministic risk
rules before anything can execute.
