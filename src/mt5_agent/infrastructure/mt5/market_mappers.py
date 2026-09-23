"""Mappers: raw MT5 market payloads -> domain models.

Handles MT5 namedtuples (`_asdict()`), plain mappings, attribute objects, and
numpy structured arrays / row sequences. Never imports MetaTrader5, never I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from mt5_agent.domain.errors import MT5DataError
from mt5_agent.domain.market import Candle, SymbolInfo, Tick, Timeframe


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
    # numpy void row or sequence-like: try field access fallback by caller.
    raise MT5DataError(f"Cannot decode {what}: unexpected type {type(raw).__name__}.")


def _field(row: Any, name: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(name, default)
    asdict = getattr(row, "_asdict", None)
    if callable(asdict):
        try:
            return asdict().get(name, default)
        except Exception:
            return default
    try:
        return row[name]  # numpy void / sequence rows
    except Exception:
        return getattr(row, name, default)


def _utc_from_epoch(seconds: Any, *, ms: Any = None) -> datetime:
    if ms is not None:
        try:
            return datetime.fromtimestamp(float(ms) / 1000.0, tz=UTC)
        except (TypeError, ValueError, OSError):
            pass
    try:
        return datetime.fromtimestamp(float(seconds), tz=UTC)
    except (TypeError, ValueError, OSError) as exc:
        raise MT5DataError(f"Invalid epoch timestamp {seconds!r}: {exc}") from exc


def map_tick(raw: Any, symbol: str) -> Tick:
    """Map MT5 `symbol_info_tick()` result to :class:`Tick`."""
    data = _as_mapping(raw, what=f"tick({symbol})")
    get = data.get if isinstance(data, Mapping) else lambda k, d=None: _field(raw, k, d)
    bid = get("bid", 0.0)
    ask = get("ask", 0.0)
    try:
        return Tick(
            symbol=symbol,
            time=_utc_from_epoch(get("time", 0), ms=get("time_msc", None)),
            bid=float(bid or 0.0),
            ask=float(ask or 0.0),
            last=float(get("last", 0.0) or 0.0),
            volume=float(get("volume", get("volume_real", 0.0)) or 0.0),
        )
    except (TypeError, ValueError) as exc:
        raise MT5DataError(f"Invalid tick payload for {symbol!r}: {exc}") from exc


def map_candle(row: Any, symbol: str, timeframe: Timeframe) -> Candle:
    """Map a single MT5 rate row to :class:`Candle`."""
    if isinstance(row, Mapping) or hasattr(row, "_asdict") or hasattr(row, "__dict__"):
        data = _as_mapping(row, what=f"candle({symbol})")

        def get(key: str, default: Any = None) -> Any:
            return data.get(key, default)
    else:

        def get(key: str, default: Any = None) -> Any:
            return _field(row, key, default)

    try:
        return Candle(
            symbol=symbol,
            timeframe=timeframe,
            time=_utc_from_epoch(get("time", 0)),
            open=float(get("open", 0.0) or 0.0),
            high=float(get("high", 0.0) or 0.0),
            low=float(get("low", 0.0) or 0.0),
            close=float(get("close", 0.0) or 0.0),
            tick_volume=int(get("tick_volume", get("tick_volume_", 0)) or 0),
            spread=int(get("spread", 0) or 0),
            real_volume=float(get("real_volume", 0.0) or 0.0),
        )
    except (TypeError, ValueError) as exc:
        raise MT5DataError(f"Invalid candle payload for {symbol!r}: {exc}") from exc


def map_candles(rows: Any, symbol: str, timeframe: Timeframe) -> list[Candle]:
    """Map MT5 `copy_rates_*` result (numpy array or sequence) to candles."""
    if rows is None:
        raise MT5DataError(f"candles({symbol}) unavailable (MT5 returned None).")
    try:
        items: Iterable[Any] = list(rows)
    except TypeError as exc:
        raise MT5DataError(f"Invalid candles payload for {symbol!r}: {exc}") from exc
    candles = [map_candle(row, symbol, timeframe) for row in items]
    if not candles:
        raise MT5DataError(f"No candles returned for {symbol!r}.")
    return candles


def map_symbol_info(raw: Any, symbol: str) -> SymbolInfo:
    """Map MT5 `symbol_info()` result to :class:`SymbolInfo`."""
    data = _as_mapping(raw, what=f"symbol_info({symbol})")
    get = data.get
    try:
        return SymbolInfo(
            symbol=str(get("name", symbol) or symbol),
            description=str(get("description", "") or ""),
            currency_base=str(get("currency_base", "") or ""),
            currency_profit=str(get("currency_profit", "") or ""),
            digits=int(get("digits", 0) or 0),
            point=float(get("point", 0.0) or 0.0),
            spread=int(get("spread", 0) or 0),
            trade_mode=int(get("trade_mode", 0) or 0),
            min_volume=float(get("volume_min", 0.0) or 0.0),
            max_volume=float(get("volume_max", 0.0) or 0.0),
            volume_step=float(get("volume_step", 0.0) or 0.0),
            contract_size=float(get("trade_contract_size", 0.0) or 0.0),
        )
    except (TypeError, ValueError) as exc:
        raise MT5DataError(f"Invalid symbol_info payload for {symbol!r}: {exc}") from exc


__all__ = ["map_candle", "map_candles", "map_symbol_info", "map_tick"]
