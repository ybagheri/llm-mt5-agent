# Strategy engine (Phase 04+)

Deterministic `Strategy.analyze(context) -> StrategySignal` abstraction.
Strategies compute objective market facts; they never call the LLM or MT5.
Phase 00 ships only the `strategies/` package placeholder.
