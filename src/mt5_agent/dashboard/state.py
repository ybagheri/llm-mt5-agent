"""Dashboard state models (JSON-serializable dicts, no I/O)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AccountSection:
    balance: float = 0.0
    equity: float = 0.0
    margin: float = 0.0
    free_margin: float = 0.0
    floating_profit: float = 0.0
    day_pnl: float | None = None
    currency: str = ""
    login: int = 0
    server: str = ""


@dataclass(frozen=True, slots=True)
class MarketSection:
    symbol: str = ""
    timeframe: str = ""
    bid: float | None = None
    ask: float | None = None
    spread_points: float | None = None
    latest_close: float | None = None
    session_open: bool = True
    server_time: str = ""


@dataclass(frozen=True, slots=True)
class AgentSection:
    state: str = "idle"
    strategy: str = ""
    direction: str = "FLAT"
    confidence: float = 0.0
    proposal_action: str = "HOLD"
    proposal_summary: str = ""
    last_cycle_ok: bool | None = None


@dataclass(frozen=True, slots=True)
class RiskSection:
    max_risk_pct: float = 0.0
    exposure_volume: float = 0.0
    max_exposure_volume: float = 0.0
    open_positions: int = 0
    max_open_positions: int = 0
    day_pnl: float | None = None
    max_daily_loss_pct: float = 0.0


@dataclass(frozen=True, slots=True)
class MemorySection:
    recent_decisions: tuple[dict[str, Any], ...] = ()
    recent_trades: tuple[dict[str, Any], ...] = ()
    recent_events: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class LLMSection:
    provider: str = "none"
    model: str = ""
    latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None


@dataclass(frozen=True, slots=True)
class DashboardState:
    """Full read-only snapshot served as JSON + HTML."""

    account: AccountSection = field(default_factory=AccountSection)
    market: MarketSection = field(default_factory=MarketSection)
    agent: AgentSection = field(default_factory=AgentSection)
    risk: RiskSection = field(default_factory=RiskSection)
    memory: MemorySection = field(default_factory=MemorySection)
    llm: LLMSection = field(default_factory=LLMSection)
    version: str = ""
    trading_mode: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "AccountSection",
    "AgentSection",
    "DashboardState",
    "LLMSection",
    "MarketSection",
    "MemorySection",
    "RiskSection",
]
