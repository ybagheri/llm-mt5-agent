"""Order service: pending-order reads (read-only)."""

from __future__ import annotations

from mt5_agent.domain.ports import OrderPort
from mt5_agent.domain.trading import Order


class OrderService:
    """Read-only pending-order queries."""

    def __init__(self, port: OrderPort) -> None:
        self._port = port

    @property
    def port(self) -> OrderPort:
        return self._port

    def pending_orders(self, symbol: str | None = None) -> list[Order]:
        return self._port.get_pending_orders(symbol)

    def count(self, symbol: str | None = None) -> int:
        return len(self.pending_orders(symbol))


__all__ = ["OrderService"]
