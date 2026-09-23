"""Configuration package."""

from __future__ import annotations

from mt5_agent.config.loader import load_settings
from mt5_agent.config.settings import AppSettings

__all__ = ["AppSettings", "load_settings"]
