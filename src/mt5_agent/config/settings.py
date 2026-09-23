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

    # --- LLM (provider-agnostic; Phase 00 stores selection only) ---
    llm_provider: str = Field(default="none")
    llm_model: str | None = Field(default=None)
    llm_timeout_s: float = Field(default=30.0, ge=1.0, le=300.0)

    @field_validator("trading_mode")
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
        return self

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> AppSettings:
        """Build settings from a plain (e.g. YAML-derived) mapping."""
        return cls(**{k: v for k, v in data.items() if v is not None})

    def masked(self) -> dict[str, Any]:
        """Return settings safe for logging (never include secrets)."""
        data = self.model_dump()
        # Secrets (passwords/API keys) are never stored on this model;
        # this hook exists so future fields are audited here.
        return data

    @staticmethod
    def default_config_path() -> Path:
        return Path("config/app.yaml")


__all__ = ["AppEnv", "AppSettings", "LogFormat", "TradingMode"]
