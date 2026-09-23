"""Settings loader: YAML file + `.env` + environment variables.

Resolution order:
  config_path arg > MT5_AGENT_CONFIG env var > config/app.yaml (if present) > defaults.
Environment variables always override file values (via pydantic-settings).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from mt5_agent.config.settings import AppSettings


def _resolve_config_path(explicit: str | Path | None) -> Path | None:
    if explicit:
        return Path(explicit)
    env_path = os.getenv("MT5_AGENT_CONFIG")
    if env_path:
        return Path(env_path)
    default = AppSettings.default_config_path()
    alt = Path("config/app.yaml")
    for candidate in (default, alt):
        if candidate.is_file():
            return candidate
    return None


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in config file '{path}': {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Config file '{path}' must contain a mapping at top level.")
    return dict(data)


def _env_overridden_keys() -> set[str]:
    """Return settings field names that have a corresponding MT5_AGENT_* env var set."""
    prefix = "MT5_AGENT_"
    keys: set[str] = set()
    for env_key in os.environ:
        if not env_key.upper().startswith(prefix):
            continue
        field = env_key[len(prefix) :].lower()
        if field:
            keys.add(field)
    return keys


def load_settings(
    config_path: str | Path | None = None,
    load_env_file: bool = True,
) -> AppSettings:
    """Load validated settings. Never raises for missing files; raises for invalid content."""
    if load_env_file:
        load_dotenv(dotenv_path=Path(".env"), override=False)
    path = _resolve_config_path(config_path)
    file_values: dict[str, Any] = _read_yaml(path) if path and path.is_file() else {}
    # pydantic-settings prioritizes init kwargs over env vars, so drop any file
    # value shadowed by an explicit MT5_AGENT_* env var to keep env-over-file.
    for key in _env_overridden_keys():
        file_values.pop(key, None)
    return AppSettings(**file_values)


__all__ = ["load_settings"]
