# Risk management

Risk controls are deterministic and execute before order submission. The LLM cannot override them.

## Current controls

- account trading permission, positive equity, and margin level;
- allowlisted symbols and permitted sessions;
- maximum proposed risk percentage;
- maximum daily loss percentage;
- account-wide open-position count;
- account-wide gross exposure including the resolved default volume;
- maximum spread in normalized points;
- mandatory stop loss and take profit;
- minimum stop distance in symbol points;
- duplicate open-position and approved-signal protection;
- cooldown between decisions;
- fail-closed behavior for unavailable daily P&L, spread, and point size.

## Mode safety

`DRY_RUN` simulates. `DEMO` requires a connected account and rejects an account reporting real trade mode. `LIVE` requires explicit opt-in and a verified connection. The system does not support unattended real-money operation as a safe default.

## Known limitation

The supplied implementation validates proposed risk percentage and bracket geometry. It does not yet calculate a full broker-specific monetary risk using tick value, contract size, conversion currency, and margin simulation for every symbol. Treat position sizing as conservative configuration, not as a guarantee.

Ambiguous order timeouts are `UNKNOWN`; never retry them blindly. Reconcile account positions, orders, and deals first.
