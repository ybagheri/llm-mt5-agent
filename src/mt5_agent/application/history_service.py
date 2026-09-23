"""History service: deals / history orders / closed-trade summaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mt5_agent.domain.errors import MT5MarketDataError
from mt5_agent.domain.ports import HistoryPort
from mt5_agent.domain.trading import Deal, Order, TradeResult

DEFAULT_LOOKBACK_DAYS = 30


class HistoryService:
    """Read-only trading-history queries."""

    def __init__(self, port: HistoryPort) -> None:
        self._port = port

    @property
    def port(self) -> HistoryPort:
        return self._port

    def deals(
        self,
        date_from: datetime,
        date_to: datetime,
        symbol: str | None = None,
    ) -> list[Deal]:
        self._check_range(date_from, date_to)
        return self._port.get_deals(date_from, date_to, symbol)

    def history_orders(
        self,
        date_from: datetime,
        date_to: datetime,
        symbol: str | None = None,
    ) -> list[Order]:
        self._check_range(date_from, date_to)
        return self._port.get_history_orders(date_from, date_to, symbol)

    def recent_deals(
        self, days: int = DEFAULT_LOOKBACK_DAYS, symbol: str | None = None
    ) -> list[Deal]:
        """Deals over the trailing `days` window (convenience for dashboards)."""
        if days < 1 or days > 3650:
            raise MT5MarketDataError(f"days must be 1..3650, got {days!r}")
        now = datetime.now(UTC)
        return self.deals(now - timedelta(days=days), now, symbol)

    def realized_profit(self, deals: list[Deal]) -> float:
        """Net realized P&L over an explicit deal list (profit+commission+swap+fee)."""
        return float(sum(d.net for d in deals))

    def closed_results(self, deals: list[Deal]) -> list[TradeResult]:
        """Aggregate deals by position_id into per-trade summaries."""
        buckets: dict[int, list[Deal]] = {}
        for deal in deals:
            buckets.setdefault(deal.position_id, []).append(deal)
        results = [
            TradeResult(
                position_id=position_id,
                symbol=items[0].symbol,
                volume=sum(d.volume for d in items),
                profit=sum(d.profit for d in items),
                commission=sum(d.commission for d in items),
                swap=sum(d.swap for d in items),
                fee=sum(d.fee for d in items),
                deals=len(items),
            )
            for position_id, items in buckets.items()
            if position_id != 0
        ]
        return sorted(results, key=lambda r: r.position_id)

    @staticmethod
    def _check_range(date_from: datetime, date_to: datetime) -> None:
        if date_to < date_from:
            raise MT5MarketDataError("date_to must be >= date_from")


__all__ = ["DEFAULT_LOOKBACK_DAYS", "HistoryService"]
