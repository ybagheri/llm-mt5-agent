# Signals and analysis

Signals are deterministic and LLM-free. The current default strategy reads the latest candle window and detects a close beyond the prior Donchian high or low. Freshness and forming-candle policy are explicit follow-up work; the LLM explains a candidate but cannot create a direction that the deterministic engine did not find.

A signal includes:

- symbol and timeframe;
- direction (`LONG`, `SHORT`, or `FLAT`);
- confidence;
- setup identifiers;
- objective facts;
- rationale;
- generation time.

A directional LLM action must match the signal direction. `FLAT` or insufficient data cannot become `BUY` or `SELL`.

The system uses price action and market structure first. Indicators should be added only when a strategy has a documented hypothesis, testable parameters, and a clear role in the risk decision. Historical evaluation must avoid look-ahead bias, incomplete candles, unrealistic fills, spread, slippage, and survivorship bias.

`WAIT` is represented by `HOLD`. It is a valid decision when context, spread, risk, session, or data quality is not adequate.
