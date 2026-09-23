"""Strategy engine: deterministic `Strategy` ABC (never calls LLM or MT5)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from mt5_agent.domain.strategy import MarketContext, StrategySignal


class Strategy(ABC):
    """Deterministic market-facts engine. Implementations must be pure."""

    name: str = "strategy"

    @abstractmethod
    def analyze(self, context: MarketContext) -> StrategySignal:
        """Compute objective facts + direction from `context`. Never raises blindly."""
        ...


__all__ = ["Strategy"]
