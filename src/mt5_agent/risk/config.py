"""Risk configuration: every limit explicit, conservative demo-first defaults."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TradingSession:
    """UTC session window [start_hour, end_hour). Overnight spans allowed."""

    start_hour: int = 0
    end_hour: int = 24

    def __post_init__(self) -> None:
        if not 0 <= self.start_hour <= 24 or not 0 <= self.end_hour <= 24:
            raise ValueError("session hours must be 0..24")
        if self.start_hour == self.end_hour:
            raise ValueError("zero-length session")

    def contains(self, hour: int) -> bool:
        if self.start_hour < self.end_hour:
            return self.start_hour <= hour < self.end_hour
        return hour >= self.start_hour or hour < self.end_hour


@dataclass(frozen=True, slots=True)
class RiskConfig:
    """Deterministic limits. The LLM can never override these."""

    max_risk_pct_per_trade: float = 1.0
    max_daily_loss_pct: float = 3.0
    max_open_positions: int = 3
    max_exposure_volume: float = 1.0
    allowed_symbols: tuple[str, ...] | None = None
    allowed_sessions: tuple[TradingSession, ...] = (TradingSession(0, 24),)
    max_spread_points: float | None = None
    require_stop_loss: bool = True
    require_take_profit: bool = True
    min_stop_points: float = 0.0
    duplicate_window_s: float = 600.0
    cooldown_s: float = 60.0
    min_margin_level_pct: float = 100.0

    def __post_init__(self) -> None:
        if self.max_risk_pct_per_trade <= 0 or self.max_risk_pct_per_trade > 100:
            raise ValueError("max_risk_pct_per_trade must be 0..100")
        if self.max_daily_loss_pct <= 0 or self.max_daily_loss_pct > 100:
            raise ValueError("max_daily_loss_pct must be 0..100")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be >= 1")
        if self.max_exposure_volume <= 0:
            raise ValueError("max_exposure_volume must be positive")
        if not self.allowed_sessions:
            raise ValueError("at least one session is required")
        if self.max_spread_points is not None and self.max_spread_points <= 0:
            raise ValueError("max_spread_points must be positive")
        if self.min_stop_points < 0:
            raise ValueError("min_stop_points must be >= 0")
        if self.duplicate_window_s < 0 or self.cooldown_s < 0:
            raise ValueError("windows must be >= 0")
        if self.min_margin_level_pct <= 0:
            raise ValueError("min_margin_level_pct must be positive")


__all__ = ["RiskConfig", "TradingSession"]
