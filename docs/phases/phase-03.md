# Phase 03 — Account, Orders, Positions and History

## Objective
Expose read-only trading state through deterministic services: account snapshot
with exposure/P&L, open positions, pending orders, historical orders/deals, and
closed-trade summaries — all as domain models.

## Scope
In scope: `AccountState/Position/Order/Deal/TradeResult` models,
`PositionPort/OrderPort/HistoryPort`, MT5 trading mappers + adapter, four
application services, unit tests with fakes, gated live test,
`scripts/check_trading.py`.
Out of scope: market data changes, strategies, order sending (Phase 08).

## Architecture
```
domain/trading.py             # Position/Order/Deal/TradeResult/AccountState
domain/ports.py               # PositionPort/OrderPort/HistoryPort
infrastructure/mt5/
  trading_mappers.py          # namedtuple/mapping rows -> domain (UTC)
  trading_adapter.py          # MT5TradingDataAdapter (all three ports)
application/
  position_service.py         # exposure/net/floating aggregations
  order_service.py            # pending reads + count
  history_service.py          # deals/orders/closed_results/realized_profit
  account_service.py          # composes connection+positions+orders
```
Adapter optionally guards on `MT5ConnectionPort.is_connected()`. History date
filtering for symbols happens domain-side (MT5 range APIs filter by
date/position/ticket, not symbol).

## Components
- `Position(ticket,symbol,side,volume,price_open,price_current,profit,swap,
  sl,tp,magic,comment,time)` + `floating/signed_volume`; `PositionSide{BUY,SELL}`.
- `Order(...)` for pending + history orders (raw MT5 type/state ints preserved).
- `Deal(...)` + `net` (profit+commission+swap+fee).
- `TradeResult(position_id,symbol,volume,profit,commission,swap,fee,deals)` +
  `net`; built by grouping deals on `position_id` (excludes 0/balance entries).
- `AccountState(account,open_positions,pending_orders,exposure_volume,
  net_volume,floating_profit)` + balance/equity/margin/free_margin/margin_level.
- Services per Scope; `HistoryService.recent_deals(days)` convenience
  (1..3650 validated).

## Interfaces
- `get_open_positions(symbol=None) -> list[Position]`
- `get_pending_orders(symbol=None) -> list[Order]`
- `get_deals(date_from,date_to,symbol=None) -> list[Deal]`
- `get_history_orders(date_from,date_to,symbol=None) -> list[Order]`
- `AccountService.get_state(symbol=None) -> AccountState`
- `HistoryService.closed_results(deals) / realized_profit(deals) / recent_deals(days)`

## Data Models
See Components. Timestamps UTC-aware; monetary values are terminal-reported
(not recomputed); exposure = sum |volume|, net = BUY−SELL signed sum.

## Configuration
No new settings. Probe: `python scripts/check_trading.py --days 7`.

## Error Handling
- Empty symbol filter / inverted date range / bad lookback: `MT5MarketDataError`.
- Guard connection offline: `MT5NotConnectedError`.
- Unknown position `type`: `MT5DataError`; `None` collections map to `[]`
  (single-item getters in Phase 01/02 still raise — unchanged).
- Only `order_send`-family remains uncalled anywhere (no execution code).

## Security Considerations
Strictly read-only (`positions_get/orders_get/history_*_get` only). No
credentials beyond Phase 01 handling; account numbers appear in local probe
output only, never logged by services.

## Testing Strategy
- `test_trading_models`: side/floating/net/margin-level/validation.
- `test_trading_mappers`: namedtuple/dict rows, bad-type/None, `map_many`.
- `test_trading_adapter`: `FakeMT5` collections, symbol filtering, range
  validation, offline guard, service aggregations (exposure −0.1 net on
  0.1 BUY + 0.2 SELL fixture), closed-result grouping incl. position_id 0 skip.
- `test_trading_live`: gated (`MT5_AGENT_RUN_LIVE_MT5_TESTS=true`), asserts
  non-negative balance/counts + typed history. CI runs `-m "not integration"`.

## Acceptance Criteria
- [x] `AccountService/PositionService/OrderService/HistoryService` exist
- [x] `AccountState/Position/Order/Deal/TradeResult` exist
- [x] Read-only operations first (no execution paths)
- [x] balance/equity/margins, positions, orders, history, exposure, P/L exposed

## Definition of Done
Boxes checked; `pytest/ruff/mypy` green; live probe verified; diff reviewed;
focused commit `feat(phase-03): ...` pushed.

## Files Added
- `src/mt5_agent/domain/trading.py`
- `src/mt5_agent/infrastructure/mt5/{trading_mappers,trading_adapter}.py`
- `src/mt5_agent/application/{account,position,order,history}_service.py`
- `tests/unit/{test_trading_models,test_trading_mappers,test_trading_adapter}.py`
- `tests/integration/test_trading_live.py`
- `scripts/check_trading.py`
- `docs/mt5/trading-state.md`

## Files Modified
- `src/mt5_agent/domain/{ports,__init__}.py`
- `src/mt5_agent/application/__init__.py`
- `src/mt5_agent/infrastructure/mt5/__init__.py`
- `README.md`, `ROADMAP.md`, `CHANGELOG.md`, `pyproject.toml` (v0.4.0)

## Dependencies
None new.

## Future Work
Phase 04: strategy engine (`Strategy.analyze(MarketContext)`) consuming Phase
02/03 domain models; observation-only `NullStrategy` first.
