# Phase 02 — Market Data Layer

## Objective
Provide a deterministic, read-only market-data layer: ticks, OHLC candles across
multiple timeframes, bid/ask + spread, and symbol metadata — exposed as domain
models so strategies never touch raw MT5 tuples/arrays.

## Scope
In scope: `Tick/Candle/SymbolInfo/MarketSnapshot/Timeframe` models,
`MarketDataPort`, MT5 mappers + `MT5MarketDataAdapter`, `MarketService`,
settings defaults, unit tests with fakes, gated live test, `check_market.py`.
Out of scope: account/orders/positions/history (Phase 03), strategies (Phase 04).

## Architecture
```
domain/market.py            # Tick/Candle/SymbolInfo/MarketSnapshot/Timeframe
domain/ports.py             # MarketDataPort (+ MT5ConnectionPort)
infrastructure/mt5/
  timeframes.py             # Timeframe -> TIMEFRAME_* resolution
  market_mappers.py         # namedtuple/mapping/numpy rows -> domain
  market_adapter.py         # copy_rates_from_pos/symbol_info_tick/symbol_info
application/market_service.py  # validation + delegation
```
Adapter optionally guards on `MT5ConnectionPort.is_connected()`; timeframe
mapping is isolated in `timeframes.py` so domain stays MT5-free.

## Components
- `Timeframe`: M1/M5/M15/M30/H1/H4/D1/W1/MN1 (MT5 subset).
- `Tick(symbol,time,bid,ask,last,volume)` + `spread/mid` helpers; validates
  positive bid/ask, `ask>=bid`.
- `Candle(symbol,timeframe,time,o/h/l/c,tick_volume,spread,real_volume)` +
  `is_bullish/body/range`; validates OHLC consistency.
- `SymbolInfo` (digits/point/spread/trade_mode/volumes/contract size).
- `MarketSnapshot(symbol,timeframe,fetched_at,candles,tick,symbol_info)` +
  `latest_candle/latest_close`.
- `MarketDataPort`: `get_tick/get_candles/get_symbol_info/get_snapshot`.
- Adapter: `get_candles` via `copy_rates_from_pos` (count 1..5000, validated);
  `get_tick` via `symbol_info_tick`; `get_symbol_info` via `symbol_info`
  (unknown -> `MT5SymbolNotFoundError`); `get_snapshot` composes candles
  (required) + tick/symbol (best-effort `None` on failure).
- `MarketService`: symbol normalization/validation, delegation.
- Settings: `mt5_default_symbol/timeframe/candles` (env-overridable).

## Interfaces
- `get_tick(symbol) -> Tick`
- `get_candles(symbol, timeframe, count=100, start_pos=0) -> list[Candle]`
  (newest last)
- `get_symbol_info(symbol) -> SymbolInfo`
- `get_snapshot(symbol, timeframe, count=100) -> MarketSnapshot`

## Data Models
See Components. All timestamps normalized to UTC-aware datetimes
(`time_msc` preferred for ticks when present).

## Configuration
- `config/app.yaml`: `mt5_default_symbol: EURUSD`, `mt5_default_timeframe: M1`,
  `mt5_default_candles: 100`.
- Env: `MT5_AGENT_MT5_DEFAULT_SYMBOL/_TIMEFRAME/_CANDLES` (via prefix).
- `scripts/check_market.py --symbol EURUSD --timeframe M1 --count 5`.

## Error Handling
- Empty/oversize symbol, `count` outside 1..5000, negative `start_pos`:
  `MT5MarketDataError`.
- Unknown symbol: `MT5SymbolNotFoundError` (probed via `symbol_info()`).
- Reads with a disconnected guard connection: `MT5NotConnectedError`.
- Empty/None payloads: `MT5DataError`/`MT5MarketDataError`; snapshot keeps
  partial data (candles required, tick/symbol optional).

## Security Considerations
Read-only: only `copy_rates_from_pos/symbol_info_tick/symbol_info` are called;
no order functions referenced. No secrets involved in market reads.

## Testing Strategy
- `test_market_models`: validation + helpers (spread/mid/bullish/range/snapshot).
- `test_market_mappers`: namedtuple/dict/sequence rows, `time_msc` precision,
  empty/None/invalid payloads.
- `test_market_adapter`: `FakeMT5` (candles/tick/symbol/unknown/failure/
  arg-validation/disconnect-guard/partial-snapshot) + `FakePort` service tests.
- `test_market_live`: gated (`MT5_AGENT_RUN_LIVE_MT5_TESTS=true`), read-only
  snapshot assert on default symbol. CI runs `-m "not integration"`.

## Acceptance Criteria
- [x] `MarketDataProvider`/`MT5MarketDataProvider` exist (`MarketDataPort`/`MT5MarketDataAdapter`)
- [x] Domain models `Tick/Candle/MarketSnapshot/SymbolInfo` exist
- [x] Ticks, OHLC, multiple timeframes, bid/ask, spread, symbol metadata supported
- [x] Strategy layer will consume domain models (no raw tuples leak past mappers)

## Definition of Done
Boxes checked; `pytest/ruff/mypy` green; live snapshot verified; diff reviewed;
focused commit `feat(phase-02): ...` pushed.

## Files Added
- `src/mt5_agent/domain/market.py`
- `src/mt5_agent/infrastructure/mt5/{timeframes,market_mappers,market_adapter}.py`
- `src/mt5_agent/application/market_service.py`
- `tests/unit/{test_market_models,test_market_mappers,test_market_adapter}.py`
- `tests/integration/test_market_live.py`
- `scripts/check_market.py`
- `docs/mt5/market-data.md`

## Files Modified
- `src/mt5_agent/domain/{errors,ports,__init__}.py`
- `src/mt5_agent/application/__init__.py`
- `src/mt5_agent/infrastructure/mt5/__init__.py`
- `src/mt5_agent/config/settings.py`, `config/app.yaml`
- `README.md`, `ROADMAP.md`, `CHANGELOG.md`, `pyproject.toml` (v0.3.0)

## Dependencies
None new (`numpy` arrives via `MetaTrader5`; mappers also accept plain
sequences so unit tests don't require it).

## Future Work
Phase 03: account/orders/positions/history services + `AccountState/Position/
Order/Deal/TradeResult` models reusing this connection.
