"""Execution domain models (no MT5 dependency)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from mt5_agent.domain.planning import TradeAction


class ExecutionMode(StrEnum):
    """DRY_RUN simulates, DEMO trades demo accounts, LIVE needs dual opt-in."""

    DRY_RUN = "DRY_RUN"
    DEMO = "DEMO"
    LIVE = "LIVE"


class ExecutionStatus(StrEnum):
    """Outcome of one execution attempt.

    SUCCESS/REJECTED/FAILED are terminal and certain. UNKNOWN means the order
    *may* have been accepted (e.g. timeout after submission): the caller must
    verify positions/orders before retrying with the same `client_id` and must
    never treat UNKNOWN as proof of failure.
    """

    SUCCESS = "SUCCESS"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """Normalized market-order intent derived from an approved proposal."""

    symbol: str
    action: TradeAction
    volume: float
    stop_loss: float = 0.0
    take_profit: float = 0.0
    magic: int = 0
    comment: str = ""
    deviation: int = 20
    client_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self) -> None:
        if self.action not in (TradeAction.BUY, TradeAction.SELL):
            raise ValueError("execution requires BUY or SELL")
        if not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if self.volume <= 0:
            raise ValueError("volume must be positive")
        if not self.client_id.strip():
            raise ValueError("client_id must be non-empty")


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    """Auditable outcome of `validate -> prepare -> order_check -> execute -> verify`."""

    client_id: str
    symbol: str
    action: TradeAction
    volume: float
    status: ExecutionStatus
    mode: ExecutionMode
    ticket: int | None = None
    deal: int | None = None
    executed_price: float | None = None
    requested_price: float | None = None
    slippage: float | None = None
    error_code: str = ""
    message: str = ""
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        object.__setattr__(self, "decided_at", _utc(self.decided_at))
        if (
            self.status == ExecutionStatus.SUCCESS
            and self.mode != ExecutionMode.DRY_RUN
            and self.ticket is None
        ):
            raise ValueError("non-dry-run SUCCESS records require a ticket")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = ["ExecutionMode", "ExecutionRecord", "ExecutionStatus", "OrderRequest"]
