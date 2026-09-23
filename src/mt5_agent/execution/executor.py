"""Execution engine: approved proposals only, DRY_RUN-first, idempotent.

Lifecycle per call: validate -> prepare -> order_check -> execute -> verify ->
record. Retries must reuse `client_id`: completed attempts are replayed from
the ledger instead of resent, so duplicate orders are impossible by retry.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from mt5_agent.domain.errors import MT5NotConnectedError
from mt5_agent.domain.execution import (
    ExecutionMode,
    ExecutionRecord,
    ExecutionStatus,
    OrderRequest,
)
from mt5_agent.domain.planning import TradeAction, TradeProposal
from mt5_agent.domain.ports import MT5ConnectionPort
from mt5_agent.infrastructure.mt5.module import load_mt5
from mt5_agent.logging_utils import audit
from mt5_agent.risk.supervisor import SupervisorDecision

logger = logging.getLogger(__name__)

TRADE_MODE_DEMO = 0
TRADE_MODE_CONTEST = 1
TRADE_MODE_REAL = 2
RETCODE_DONE = 10009
RETCODE_DONE_PARTIAL = 10010


class TradeExecutor(ABC):
    """Abstract executor: `SupervisorDecision` in, `ExecutionRecord` out."""

    @abstractmethod
    def execute(
        self, decision: SupervisorDecision, *, client_id: str | None = None
    ) -> ExecutionRecord:
        """Execute an approved decision. Never raises for market outcomes."""
        ...


class MT5TradeExecutor(TradeExecutor):
    """MT5-backed executor. Default mode is DRY_RUN (no terminal calls)."""

    def __init__(
        self,
        *,
        mode: ExecutionMode = ExecutionMode.DRY_RUN,
        allow_live: bool = False,
        connection: MT5ConnectionPort | None = None,
        mt5_module: Any | None = None,
        default_volume: float = 0.01,
        magic: int = 0,
        deviation: int = 20,
    ) -> None:
        if default_volume <= 0:
            raise ValueError("default_volume must be positive")
        self._mode = mode
        self._allow_live = allow_live
        self._connection = connection
        self._mt5 = mt5_module
        self._default_volume = default_volume
        self._magic = magic
        self._deviation = deviation
        self._ledger: dict[str, ExecutionRecord] = {}

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    @property
    def ledger(self) -> dict[str, ExecutionRecord]:
        return dict(self._ledger)

    # -- lifecycle -------------------------------------------------------
    def execute(
        self, decision: SupervisorDecision, *, client_id: str | None = None
    ) -> ExecutionRecord:
        key = client_id or _new_id()
        if key in self._ledger:  # idempotent replay: never resend
            return self._ledger[key]
        record = self._run(decision, key)
        self._ledger[key] = record
        audit(
            logger,
            "order_result",
            client_id=key,
            symbol=record.symbol,
            action=record.action.value,
            status=record.status.value,
            mode=record.mode.value,
            ticket=record.ticket,
            message=record.message,
        )
        return record

    def _run(self, decision: SupervisorDecision, client_id: str) -> ExecutionRecord:
        proposal = decision.proposal
        if not decision.approved:
            return self._record(
                client_id,
                proposal,
                ExecutionStatus.REJECTED,
                f"supervisor rejected: {','.join(decision.codes) or 'unknown'}",
            )
        if proposal.action == TradeAction.HOLD:
            return self._record(
                client_id, proposal, ExecutionStatus.REJECTED, "HOLD is not executable"
            )
        if self._mode == ExecutionMode.LIVE and not self._allow_live:
            return self._record(
                client_id,
                proposal,
                ExecutionStatus.REJECTED,
                "live trading disabled (allow_live=False)",
            )
        try:
            request = self._to_request(proposal, client_id)
        except ValueError as exc:
            return self._record(client_id, proposal, ExecutionStatus.REJECTED, str(exc))
        if self._mode == ExecutionMode.DRY_RUN:
            return ExecutionRecord(
                client_id,
                request.symbol,
                request.action,
                request.volume,
                ExecutionStatus.SUCCESS,
                self._mode,
                message="DRY_RUN simulated fill (no terminal calls)",
            )
        try:
            return self._execute_live(request, proposal)
        except MT5NotConnectedError as exc:
            return self._record(
                client_id,
                proposal,
                ExecutionStatus.FAILED,
                f"{exc} Reconnect, re-verify account/positions/orders, "
                "then retry with the same client_id.",
            )
        except (TimeoutError, OSError) as exc:
            # Ambiguous: the order may have reached the server. A timeout is
            # NOT proof of failure — verify before any retry (same client_id).
            return self._record(
                client_id,
                proposal,
                ExecutionStatus.UNKNOWN,
                f"ambiguous result after {type(exc).__name__}: {exc}. "
                "Verify positions/orders before retrying with the same client_id.",
            )
        except Exception as exc:  # terminal failures become FAILED records, never raise
            return self._record(
                client_id, proposal, ExecutionStatus.FAILED, f"{type(exc).__name__}: {exc}"
            )

    def _execute_live(self, request: OrderRequest, proposal: TradeProposal) -> ExecutionRecord:
        mt5 = self._require_module()
        if self._connection is not None and not self._connection.is_connected():
            raise MT5NotConnectedError("Not connected. Call connect() first.")
        if self._mode == ExecutionMode.DEMO and self._trade_mode() == TRADE_MODE_REAL:
            return self._record(
                request.client_id,
                proposal,
                ExecutionStatus.REJECTED,
                "DEMO mode refused on a real account",
            )
        audit(
            logger,
            "order_submitted",
            client_id=request.client_id,
            symbol=request.symbol,
            action=request.action.value,
            volume=request.volume,
            mode=self._mode.value,
        )
        tick = mt5.symbol_info_tick(request.symbol)
        if tick is None:
            return self._record(
                request.client_id, proposal, ExecutionStatus.FAILED, f"no tick for {request.symbol}"
            )
        price = float(tick.ask if request.action == TradeAction.BUY else tick.bid)
        payload = self._payload(mt5, request, price)
        checked = mt5.order_check(payload)
        if checked is None or int(getattr(checked, "retcode", -1)) != RETCODE_DONE:
            return self._record(
                request.client_id,
                proposal,
                ExecutionStatus.FAILED,
                f"order_check failed: {getattr(checked, 'comment', mt5.last_error())}",
                error_code=str(getattr(checked, "retcode", "none")),
                requested_price=price,
            )
        result = mt5.order_send(payload)
        if result is None or int(getattr(result, "retcode", -1)) not in (
            RETCODE_DONE,
            RETCODE_DONE_PARTIAL,
        ):
            return self._record(
                request.client_id,
                proposal,
                ExecutionStatus.FAILED,
                f"order_send failed: {getattr(result, 'comment', mt5.last_error())}",
                error_code=str(getattr(result, "retcode", "none")),
                requested_price=price,
            )
        executed = float(getattr(result, "price", price) or price)
        verified = self._verify(mt5, int(getattr(result, "order", 0) or 0))
        return ExecutionRecord(
            request.client_id,
            request.symbol,
            request.action,
            request.volume,
            ExecutionStatus.SUCCESS,
            self._mode,
            ticket=int(getattr(result, "order", 0) or 0) or None,
            deal=int(getattr(result, "deal", 0) or 0) or None,
            executed_price=executed,
            requested_price=price,
            slippage=executed - price,
            message="verified fill"
            if verified
            else "fill assumed from retcode (position not yet visible)",
        )

    # -- helpers ------------------------------------------------------------
    def _to_request(self, proposal: TradeProposal, client_id: str) -> OrderRequest:
        return OrderRequest(
            symbol=proposal.symbol,
            action=proposal.action,
            volume=proposal.volume or self._default_volume,
            stop_loss=proposal.stop_loss or 0.0,
            take_profit=proposal.take_profit or 0.0,
            magic=self._magic,
            deviation=self._deviation,
            client_id=client_id,
        )

    def _payload(self, mt5: Any, request: OrderRequest, price: float) -> dict[str, Any]:
        order_type = (
            mt5.ORDER_TYPE_BUY if request.action == TradeAction.BUY else mt5.ORDER_TYPE_SELL
        )
        return {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": request.symbol,
            "volume": request.volume,
            "type": order_type,
            "price": price,
            "sl": request.stop_loss,
            "tp": request.take_profit,
            "deviation": request.deviation,
            "magic": request.magic,
            "comment": f"llm-mt5-agent:{request.client_id[:8]}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

    def _verify(self, mt5: Any, order_ticket: int) -> bool:
        if order_ticket <= 0:
            return False
        try:
            found = mt5.positions_get(ticket=order_ticket)
        except Exception:
            return False
        return bool(found)

    def _trade_mode(self) -> int:
        if self._connection is None:
            return TRADE_MODE_DEMO
        try:
            return int(self._connection.get_account_info().trade_mode)
        except Exception:
            return TRADE_MODE_REAL  # unknown: fail closed for DEMO

    def _require_module(self) -> Any:
        if self._mt5 is None:
            self._mt5 = load_mt5()
        return self._mt5

    def _record(
        self,
        client_id: str,
        proposal: TradeProposal,
        status: ExecutionStatus,
        message: str,
        *,
        error_code: str = "",
        requested_price: float | None = None,
    ) -> ExecutionRecord:
        return ExecutionRecord(
            client_id,
            proposal.symbol,
            proposal.action,
            proposal.volume or self._default_volume,
            status,
            self._mode,
            error_code=error_code,
            message=message,
            requested_price=requested_price,
            decided_at=datetime.now(UTC),
        )


def _new_id() -> str:
    import uuid

    return uuid.uuid4().hex


__all__ = [
    "MT5TradeExecutor",
    "RETCODE_DONE",
    "RETCODE_DONE_PARTIAL",
    "TRADE_MODE_CONTEST",
    "TRADE_MODE_DEMO",
    "TRADE_MODE_REAL",
    "TradeExecutor",
]
