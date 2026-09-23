# MT5 integration (Phase 01+)

The official `MetaTrader5` Python package is a Windows-only adapter around the
MT5 terminal. Domain code must never import it; all access goes through
`infrastructure/` gateways behind `domain` interfaces (polling/sync/execution
separated so an MQL5 event bridge can be added later).

No MT5 code exists in Phase 00.
