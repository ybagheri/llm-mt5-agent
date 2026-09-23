"""Guarded loader for the official MetaTrader5 package.

The package is Windows-only and requires a running MT5 terminal for live calls.
This module only *imports* the package; connection logic lives in the adapter.
"""

from __future__ import annotations

import sys
from typing import Any

from mt5_agent.domain.errors import MT5NotAvailableError


def load_mt5() -> Any:
    """Import and return the MetaTrader5 module.

    Raises:
        MT5NotAvailableError: when the package cannot be used here.
    """
    if sys.platform != "win32":
        raise MT5NotAvailableError(
            "MetaTrader5 is only supported on Windows "
            f"(current platform: {sys.platform}). "
            "Use a FakeMT5ConnectionPort double in tests."
        )
    try:
        import MetaTrader5
    except ImportError as exc:
        raise MT5NotAvailableError(
            "MetaTrader5 package is not installed. "
            "Install with: pip install MetaTrader5 (Windows only)."
        ) from exc
    return MetaTrader5


__all__ = ["load_mt5"]
