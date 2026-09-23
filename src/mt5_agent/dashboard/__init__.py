"""Dashboard layer: read-only web state (no trading actions, ever)."""

from __future__ import annotations

from mt5_agent.dashboard.app import DashboardApp, DashboardHandler
from mt5_agent.dashboard.costs import estimate_cost_usd
from mt5_agent.dashboard.provider import DashboardStateProvider
from mt5_agent.dashboard.state import (
    AccountSection,
    AgentSection,
    DashboardState,
    LLMSection,
    MarketSection,
    MemorySection,
    RiskSection,
)

__all__ = [
    "AccountSection",
    "AgentSection",
    "DashboardApp",
    "DashboardHandler",
    "DashboardState",
    "DashboardStateProvider",
    "LLMSection",
    "MarketSection",
    "MemorySection",
    "RiskSection",
    "estimate_cost_usd",
]
