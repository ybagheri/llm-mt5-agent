# Market data (Phase 02)

Read-only market data over the Phase 01 connection. Strategies consume domain
models (`Tick/Candle/SymbolInfo/MarketSnapshot/Timeframe`) — never MT5 tuples.

## Quick probe
```powershell
python scripts/check_market.py --symbol EURUSD --timeframe M1 --count 5
```
Output: symbol/timeframe/candle count/latest close, tick bid/ask/spread, and
symbol digits/spread. Exit 0 on success, 1 on connection/fetch failure.

## Architecture
- `MarketDataPort` (`domain/ports.py`) — the interface strategies code against.
- `MT5MarketDataAdapter` — MT5 calls: `copy_rates_from_pos` (candles),
  `symbol_info_tick` (tick), `symbol_info` (metadata). Optional guard on
  `MT5ConnectionPort.is_connected()`.
- `market_mappers.py` — namedtuple/mapping/numpy-row -> domain (UTC datetimes).
- `MarketService` — symbol/count validation, snapshot convenience.

## Timeframes
`M1 M5 M15 M30 H1 H4 D1 W1 MN1` -> `TIMEFRAME_*` via `timeframes.py`.
`get_candles(symbol, tf, count=100, start_pos=0)` returns newest-last; count is
clamped to 1..5000 (`MAX_CANDLES`).

## Errors
`MT5MarketDataError` (bad args/fetch failure), `MT5SymbolNotFoundError`
(unknown symbol), `MT5NotConnectedError` (guard connection offline).
`get_snapshot` requires candles; tick/symbol fall back to `None` so partial
snapshots still work.
