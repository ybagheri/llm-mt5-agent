"""MT5 timeframe resolution (isolated so domain stays MT5-free)."""

from __future__ import annotations

from typing import Any

from mt5_agent.domain.errors import MT5MarketDataError
from mt5_agent.domain.market import Timeframe


def resolve_timeframe(mt5: Any, timeframe: Timeframe) -> Any:
    """Map a domain :class:`Timeframe` to the MT5 `TIMEFRAME_*` constant."""
    name = f"TIMEFRAME_{timeframe.value}"
    try:
        return getattr(mt5, name)
    except AttributeError as exc:
        raise MT5MarketDataError(f"Unsupported timeframe: {timeframe.value}") from exc


__all__ = ["resolve_timeframe"]
