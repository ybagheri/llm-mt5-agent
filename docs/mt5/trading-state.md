# Trading state (Phase 03)

Read-only account/positions/orders/history over the Phase 01 connection.
Services return domain models (`AccountState/Position/Order/Deal/TradeResult`).

## Quick probe
```powershell
python scripts/check_trading.py --days 7
```
Prints account (balance/equity/margin/level/floating), position/order counts,
exposure + net volumes, open positions, pending orders, and recent-deal /
closed-trade summaries. Exit 0 on success.

## Services
- `AccountService(connection, positions, orders).get_state()` — balance, equity,
  free margin, margin + margin level, exposure, net volume, floating P&L.
- `PositionService` — `open_positions()`, `exposure_volume()`, `net_volume()`,
  `floating_profit()`.
- `OrderService` — `pending_orders()`, `count()`.
- `HistoryService` — `deals()` / `history_orders()` over `[date_from, date_to]`,
  `recent_deals(days)`, `realized_profit(deals)`, `closed_results(deals)`
  (grouped by `position_id`, net = profit+commission+swap+fee).

## MT5 calls used
`positions_get`, `orders_get`, `history_deals_get`, `history_orders_get` only —
no `order_send`/`order_check` anywhere in the codebase.
