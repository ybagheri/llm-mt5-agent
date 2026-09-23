"""Mappers: raw MT5 namedtuples -> domain models.

MT5 returns namedtuples exposing `_asdict()`. Mappers accept those, plain
mappings, or attribute objects so unit tests can use light fakes. They never
import MetaTrader5 and never perform I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mt5_agent.domain.account import AccountInfo
from mt5_agent.domain.errors import MT5DataError
from mt5_agent.domain.terminal import TerminalInfo


def _coerce_mapping(raw: Any, *, what: str) -> Mapping[str, Any]:
    if raw is None:
        raise MT5DataError(f"{what} is unavailable (MT5 returned None).")
    asdict = getattr(raw, "_asdict", None)
    if callable(asdict):
        try:
            data = asdict()
        except Exception as exc:
            raise MT5DataError(f"Cannot decode {what}: {exc}") from exc
        if isinstance(data, Mapping):
            return data
    if isinstance(raw, Mapping):
        return raw
    # Fallback: attribute objects (e.g. SimpleNamespace fakes).
    if hasattr(raw, "__dict__"):
        return dict(vars(raw))
    raise MT5DataError(f"Cannot decode {what}: unexpected type {type(raw).__name__}.")


def _get(data: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in data and data[name] is not None:
            return data[name]
    return default


def map_account_info(raw: Any) -> AccountInfo:
    """Map MT5 `account_info()` result to :class:`AccountInfo`."""
    data = _coerce_mapping(raw, what="account_info")
    try:
        return AccountInfo(
            login=int(_get(data, "login", default=0) or 0),
            server=str(_get(data, "server", default="") or ""),
            currency=str(_get(data, "currency", default="") or ""),
            balance=float(_get(data, "balance", default=0.0) or 0.0),
            equity=float(_get(data, "equity", default=0.0) or 0.0),
            margin=float(_get(data, "margin", default=0.0) or 0.0),
            free_margin=float(_get(data, "margin_free", "free_margin", default=0.0) or 0.0),
            profit=float(_get(data, "profit", default=0.0) or 0.0),
            leverage=int(_get(data, "leverage", default=0) or 0),
            trade_allowed=bool(_get(data, "trade_allowed", default=False)),
            name=str(_get(data, "name", default="") or ""),
        )
    except (TypeError, ValueError) as exc:
        raise MT5DataError(f"Invalid account_info payload: {exc}") from exc


def map_terminal_info(raw: Any) -> TerminalInfo:
    """Map MT5 `terminal_info()` result to :class:`TerminalInfo`."""
    data = _coerce_mapping(raw, what="terminal_info")
    try:
        return TerminalInfo(
            company=str(_get(data, "company", default="") or ""),
            name=str(_get(data, "name", default="") or ""),
            path=str(_get(data, "path", default="") or ""),
            trade_allowed=bool(_get(data, "trade_allowed", default=False)),
            connected=bool(_get(data, "connected", default=False)),
            build=int(_get(data, "build", default=0) or 0),
            max_bars=int(_get(data, "maxbars", "max_bars", default=0) or 0),
        )
    except (TypeError, ValueError) as exc:
        raise MT5DataError(f"Invalid terminal_info payload: {exc}") from exc


__all__ = ["map_account_info", "map_terminal_info"]
