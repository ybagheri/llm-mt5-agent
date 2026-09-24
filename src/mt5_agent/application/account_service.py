"""Account service: balance/equity/margin + exposure / P&L snapshot."""

from __future__ import annotations

from datetime import UTC, datetime

from mt5_agent.domain.ports import HistoryPort, MT5ConnectionPort, OrderPort, PositionPort
from mt5_agent.domain.trading import AccountState


class AccountService:
    """Composes connection + position + order ports into `AccountState`."""

    def __init__(
        self,
        connection: MT5ConnectionPort,
        positions: PositionPort,
        orders: OrderPort,
        history: HistoryPort | None = None,
    ) -> None:
        self._connection = connection
        self._positions = positions
        self._orders = orders
        self._history = history

    def get_state(self, symbol: str | None = None) -> AccountState:
        """Build the current account snapshot (read-only)."""
        account = self._connection.get_account_info()
        open_positions = self._positions.get_open_positions(symbol)
        pending = self._orders.get_pending_orders(symbol)
        day_realized_pnl = None
        if self._history is not None:
            now = datetime.now(UTC)
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            day_realized_pnl = float(sum(deal.net for deal in self._history.get_deals(start, now)))
        return AccountState(
            account=account,
            open_positions=len(open_positions),
            pending_orders=len(pending),
            exposure_volume=float(sum(p.volume for p in open_positions)),
            net_volume=float(sum(p.signed_volume for p in open_positions)),
            floating_profit=float(sum(p.floating for p in open_positions)),
            day_realized_pnl=day_realized_pnl,
        )


__all__ = ["AccountService"]
