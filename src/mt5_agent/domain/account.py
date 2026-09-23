"""Account domain model (pure — no MT5 dependency)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AccountInfo:
    """Snapshot of the current trading account (read-only, Phase 01)."""

    login: int
    server: str
    currency: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    profit: float
    leverage: int = 0
    trade_allowed: bool = False
    name: str = ""


__all__ = ["AccountInfo"]
