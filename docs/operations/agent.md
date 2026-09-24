# Agent operations (Phase 10)

## Run
```powershell
python scripts/run_agent.py --cycles 1                        # one dry-run cycle
python scripts/run_agent.py --loop --interval 60              # continuous
python scripts/run_agent.py --symbols EURUSD,XAUUSD --cycles 2
```
Ctrl+C (or SIGTERM) stops gracefully after the current cycle. Exit 0 when all
cycles are `ok`, 1 otherwise. Without an LLM provider configured, planning
degrades to HOLD and the run stays fully offline-capable (market reads only).

## Lifecycle
Each `run_cycle()` records nine `StageOutcome`s: OBSERVE → CONTEXT →
STRATEGY → MEMORY → PLAN → SUPERVISE → EXECUTE → VERIFY → MEMORY_UPDATE.
EXECUTE fires only for approved directional decisions (mode-gated executor);
everything else is recorded as SKIPPED with a reason. Memory facades receive
signal/proposal/decision/execution/observation/outcome rows per cycle, and
the next cycle's Planner sees recent notes as `MemoryNote`s.

## Signal selection
Strategies are evaluated in registration order, but the Planner sees the
*primary* signal: the first directional (LONG/SHORT) signal, falling back to
the first entry (usually the always-FLAT `NullStrategy` baseline) when nothing
is directional — see `select_primary()` in `domain/strategy.py`. Registration
order therefore does not gate directional signals. `ContextBuilder.
build_planner_input(..., signal_index=N)` pins strategy N explicitly for
debugging; the default (`None`) uses automatic selection.

## Configuration
`agent_symbols`, `agent_interval_s`, `agent_candle_count` (`MT5_AGENT_AGENT_*`);
all Phase 01–09 settings apply unchanged.
