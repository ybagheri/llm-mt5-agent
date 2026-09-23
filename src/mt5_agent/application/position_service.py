"""Position service: open-position reads + exposure / floating P&L."""

from __future__ import annotations

from mt5_agent.domain.ports import PositionPort
from mt5_agent.domain.trading import Position


class PositionService:
    """Read-only position queries."""

    def __init__(self, port: PositionPort) -> None:
        self._port = port

    @property
    def port(self) -> PositionPort:
        return self._port

    def open_positions(self, symbol: str | None = None) -> list[Position]:
        return self._port.get_open_positions(symbol)

    def exposure_volume(self, symbol: str | None = None) -> float:
        """Gross open volume (sum of |volume|)."""
        return float(sum(p.volume for p in self.open_positions(symbol)))

    def net_volume(self, symbol: str | None = None) -> float:
        """Net open volume (BUY positive, SELL negative)."""
        return float(sum(p.signed_volume for p in self.open_positions(symbol)))

    def floating_profit(self, symbol: str | None = None) -> float:
        """Floating P&L incl. swaps."""
        return float(sum(p.floating for p in self.open_positions(symbol)))


__all__ = ["PositionService"]
