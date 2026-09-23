"""Application settings: env-var-first, YAML-backed, validated with Pydantic.

Precedence (highest wins):
  1. Explicit constructor kwargs
  2. Environment variables (optionally loaded from `.env`)
  3. YAML config file (`config/app.yaml` by default)
  4. Built-in safe defaults (demo-first: trading_mode=dry_run, live disabled)

Safety invariant: live trading can never be enabled by default.
`trading_mode` defaults to ``dry_run`` and `enable_live_trading` defaults to False.
Any attempt to use ``live`` mode without explicit opt-in raises during validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from mt5_agent.domain.terminal import ConnectionConfig
from mt5_agent.risk.config import RiskConfig, TradingSession

TradingMode = Literal["dry_run", "demo", "live"]
LogFormat = Literal["json", "text"]
AppEnv = Literal["development", "testing", "production"]


class AppSettings(BaseSettings):
    """Validated application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MT5_AGENT_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="llm-mt5-agent")
    env: AppEnv = Field(default="development")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_format: LogFormat = Field(default="json")

    # --- Trading safety (demo-first) ---
    trading_mode: TradingMode = Field(default="dry_run")
    enable_live_trading: bool = Field(default=False)

    # --- MT5 connection (no secrets here; secrets come from env only) ---
    mt5_login: int | None = Field(default=None)
    mt5_server: str | None = Field(default=None)
    mt5_path: str | None = Field(default=None)
    mt5_timeout_ms: int = Field(default=60_000, ge=1_000, le=600_000)
    mt5_portable: bool = Field(default=False)
    mt5_default_symbol: str = Field(default="EURUSD")
    mt5_default_timeframe: str = Field(default="M1")
    mt5_default_candles: int = Field(default=100, ge=1, le=5000)

    def to_connection_config(self) -> ConnectionConfig:
        """Derive the non-secret MT5 connection config (safe to log)."""
        return ConnectionConfig(
            timeout_ms=self.mt5_timeout_ms,
            portable=self.mt5_portable,
            path=self.mt5_path,
            login=self.mt5_login,
            server=self.mt5_server,
        )

    # --- LLM (provider-agnostic; key via env only, never logged) ---
    llm_provider: str = Field(default="none")
    llm_model: str | None = Field(default=None)
    llm_api_key: str | None = Field(default=None)
    llm_base_url: str | None = Field(default=None)
    llm_timeout_s: float = Field(default=30.0, ge=1.0, le=300.0)

    # --- Risk limits (deterministic; the LLM can never override these) ---
    risk_max_risk_pct: float = Field(default=1.0, gt=0, le=100)
    risk_max_daily_loss_pct: float = Field(default=3.0, gt=0, le=100)
    risk_max_positions: int = Field(default=3, ge=1)
    risk_max_exposure: float = Field(default=1.0, gt=0)
    risk_allowed_symbols: str | None = Field(default=None)
    risk_allowed_sessions: str = Field(default="0-24")
    risk_max_spread_points: float | None = Field(default=None)
    risk_require_stop_loss: bool = Field(default=True)
    risk_require_take_profit: bool = Field(default=True)
    risk_min_stop_points: float = Field(default=0.0, ge=0)
    risk_duplicate_window_s: float = Field(default=600.0, ge=0)
    risk_cooldown_s: float = Field(default=60.0, ge=0)
    risk_min_margin_level_pct: float = Field(default=100.0, gt=0)

    # --- Execution (DRY_RUN default; LIVE needs explicit dual opt-in) ---
    execution_mode: Literal["dry_run", "demo", "live"] = Field(default="dry_run")
    execution_default_volume: float = Field(default=0.01, gt=0)
    execution_magic: int = Field(default=0, ge=0)
    execution_deviation: int = Field(default=20, ge=0)

    # --- Memory (SQLite today; same domain contract for future backends) ---
    memory_db_path: str = Field(default="data/memory.db")
    memory_short_term_keep: int = Field(default=100, ge=1)
    memory_trade_keep: int = Field(default=500, ge=1)
    memory_world_keep: int = Field(default=200, ge=1)
    memory_strategy_keep: int = Field(default=200, ge=1)

    # --- Agent loop (Phase 10; every stage observable, graceful shutdown) ---
    agent_symbols: str = Field(default="EURUSD")
    agent_interval_s: float = Field(default=60.0, ge=0)
    agent_candle_count: int = Field(default=50, ge=5, le=5000)

    # --- Dashboard (Phase 11; read-only, loopback by default) ---
    dashboard_host: str = Field(default="127.0.0.1")
    dashboard_port: int = Field(default=8080, ge=1, le=65535)
    dashboard_refresh_s: int = Field(default=15, ge=5, le=300)

    def agent_symbol_list(self) -> list[str]:
        """Parse `agent_symbols` CSV (safe to log)."""
        symbols = [s.strip() for s in self.agent_symbols.split(",") if s.strip()]
        if not symbols:
            raise ValueError("agent_symbols must list at least one symbol")
        return symbols

    def to_risk_config(self) -> RiskConfig:
        """Build the deterministic risk config (safe to log)."""
        symbols: tuple[str, ...] | None = None
        if self.risk_allowed_symbols and self.risk_allowed_symbols.strip():
            symbols = (
                tuple(s.strip() for s in self.risk_allowed_symbols.split(",") if s.strip()) or None
            )
        sessions = tuple(
            TradingSession(start, end) for start, end in _parse_sessions(self.risk_allowed_sessions)
        )
        return RiskConfig(
            max_risk_pct_per_trade=self.risk_max_risk_pct,
            max_daily_loss_pct=self.risk_max_daily_loss_pct,
            max_open_positions=self.risk_max_positions,
            max_exposure_volume=self.risk_max_exposure,
            allowed_symbols=symbols,
            allowed_sessions=sessions,
            max_spread_points=self.risk_max_spread_points,
            require_stop_loss=self.risk_require_stop_loss,
            require_take_profit=self.risk_require_take_profit,
            min_stop_points=self.risk_min_stop_points,
            duplicate_window_s=self.risk_duplicate_window_s,
            cooldown_s=self.risk_cooldown_s,
            min_margin_level_pct=self.risk_min_margin_level_pct,
        )

    @field_validator("trading_mode", "execution_mode")
    @classmethod
    def _normalize_trading_mode(cls, v: str) -> str:
        return v.lower().strip()

    @model_validator(mode="after")
    def _enforce_demo_first(self) -> AppSettings:
        if self.trading_mode == "live" and not self.enable_live_trading:
            raise ValueError(
                "trading_mode='live' requires MT5_AGENT_ENABLE_LIVE_TRADING=true. "
                "Live trading is never enabled by default."
            )
        if self.execution_mode == "live" and not self.enable_live_trading:
            raise ValueError(
                "execution_mode='live' requires MT5_AGENT_ENABLE_LIVE_TRADING=true. "
                "Live trading is never enabled by default."
            )
        return self

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> AppSettings:
        """Build settings from a plain (e.g. YAML-derived) mapping."""
        return cls(**{k: v for k, v in data.items() if v is not None})

    def masked(self) -> dict[str, Any]:
        """Return settings safe for logging (secrets redacted)."""
        data = self.model_dump()
        if data.get("llm_api_key"):
            data["llm_api_key"] = "***"
        return data

    @staticmethod
    def default_config_path() -> Path:
        return Path("config/app.yaml")


def _parse_sessions(spec: str) -> list[tuple[int, int]]:
    """Parse '0-24' or '7-12,13-21' into (start, end) hour pairs."""
    pairs: list[tuple[int, int]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            start_s, end_s = part.split("-", 1)
            pairs.append((int(start_s), int(end_s)))
        except ValueError as exc:
            raise ValueError(f"invalid session spec {part!r} (expected H-H)") from exc
    if not pairs:
        raise ValueError("at least one session is required")
    return pairs


__all__ = ["AppEnv", "AppSettings", "LogFormat", "TradingMode"]
