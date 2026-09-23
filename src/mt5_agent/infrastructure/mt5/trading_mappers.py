"""Mappers: raw MT5 trading payloads -> domain models (no MT5 import, no I/O)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from mt5_agent.domain.errors import MT5DataError
from mt5_agent.domain.trading import Deal, Order, Position, PositionSide


def _as_mapping(raw: Any, *, what: str) -> Mapping[str, Any]:
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
    if hasattr(raw, "__dict__"):
        return dict(vars(raw))
    raise MT5DataError(f"Cannot decode {what}: unexpected type {type(raw).__name__}.")


def _utc_from_epoch(seconds: Any) -> datetime:
    try:
        return datetime.fromtimestamp(float(seconds), tz=UTC)
    except (TypeError, ValueError, OSError) as exc:
        raise MT5DataError(f"Invalid epoch timestamp {seconds!r}: {exc}") from exc


def map_position(raw: Any) -> Position:
    """Map MT5 `positions_get()` row to :class:`Position`."""
    data = _as_mapping(raw, what="position")
    try:
        side = PositionSide(int(data.get("type", 0)))
    except ValueError as exc:
        raise MT5DataError(f"Unknown position type {data.get('type')!r}: {exc}") from exc
    try:
        return Position(
            ticket=int(data.get("ticket", 0) or 0),
            symbol=str(data.get("symbol", "") or ""),
            side=side,
            volume=float(data.get("volume", 0.0) or 0.0),
            price_open=float(data.get("price_open", 0.0) or 0.0),
            price_current=float(data.get("price_current", 0.0) or 0.0),
            profit=float(data.get("profit", 0.0) or 0.0),
            swap=float(data.get("swap", 0.0) or 0.0),
            stop_loss=float(data.get("sl", 0.0) or 0.0),
            take_profit=float(data.get("tp", 0.0) or 0.0),
            magic=int(data.get("magic", 0) or 0),
            comment=str(data.get("comment", "") or ""),
            time=_utc_from_epoch(data.get("time", 0)),
        )
    except (TypeError, ValueError) as exc:
        raise MT5DataError(f"Invalid position payload: {exc}") from exc


def map_order(raw: Any, *, what: str = "order") -> Order:
    """Map MT5 `orders_get()` / `history_orders_get()` row to :class:`Order`."""
    data = _as_mapping(raw, what=what)
    try:
        return Order(
            ticket=int(data.get("ticket", 0) or 0),
            symbol=str(data.get("symbol", "") or ""),
            order_type=int(data.get("type", 0) or 0),
            volume_current=float(data.get("volume_current", 0.0) or 0.0),
            volume_initial=float(data.get("volume_initial", 0.0) or 0.0),
            price_open=float(data.get("price_open", 0.0) or 0.0),
            stop_loss=float(data.get("sl", 0.0) or 0.0),
            take_profit=float(data.get("tp", 0.0) or 0.0),
            price_current=float(data.get("price_current", 0.0) or 0.0),
            magic=int(data.get("magic", 0) or 0),
            comment=str(data.get("comment", "") or ""),
            time_setup=_utc_from_epoch(data.get("time_setup", data.get("time_done", 0))),
            state=int(data.get("state", 0) or 0),
        )
    except (TypeError, ValueError) as exc:
        raise MT5DataError(f"Invalid {what} payload: {exc}") from exc


def map_deal(raw: Any) -> Deal:
    """Map MT5 `history_deals_get()` row to :class:`Deal`."""
    data = _as_mapping(raw, what="deal")
    try:
        return Deal(
            ticket=int(data.get("ticket", 0) or 0),
            order_ticket=int(data.get("order_ticket", 0) or 0),
            position_id=int(data.get("position_id", 0) or 0),
            symbol=str(data.get("symbol", "") or ""),
            deal_type=int(data.get("type", 0) or 0),
            entry=int(data.get("entry", 0) or 0),
            volume=float(data.get("volume", 0.0) or 0.0),
            price=float(data.get("price", 0.0) or 0.0),
            profit=float(data.get("profit", 0.0) or 0.0),
            commission=float(data.get("commission", 0.0) or 0.0),
            swap=float(data.get("swap", 0.0) or 0.0),
            fee=float(data.get("fee", 0.0) or 0.0),
            magic=int(data.get("magic", 0) or 0),
            comment=str(data.get("comment", "") or ""),
            time=_utc_from_epoch(data.get("time", 0)),
        )
    except (TypeError, ValueError) as exc:
        raise MT5DataError(f"Invalid deal payload: {exc}") from exc


def map_many(rows: Any, mapper: Any, *, what: str) -> list[Any]:
    """Map a sequence/None MT5 collection; None means empty collection."""
    if rows is None:
        return []
    try:
        items: Iterable[Any] = list(rows)
    except TypeError as exc:
        raise MT5DataError(f"Invalid {what} payload: {exc}") from exc
    return [mapper(row) for row in items]


__all__ = ["map_deal", "map_many", "map_order", "map_position"]
