"""Structured logging: JSON (default) or human-readable text.

Usage:
    from mt5_agent.logging_utils import configure_logging, get_logger
    configure_logging(level="INFO", log_format="json")
    logger = get_logger(__name__)
    logger.info("market snapshot", extra={"extra_fields": {"symbol": "EURUSD"}})

Rules:
  - Never log secrets (passwords, API keys, tokens). Callers must not put them
    in messages or `extra_fields`.
  - `extra_fields` dict in `extra` is merged into the JSON record.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra_fields = getattr(record, "extra_fields", None)
        if isinstance(extra_fields, dict):
            for key, value in extra_fields.items():
                if key not in payload:
                    payload[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extra_fields = getattr(record, "extra_fields", None)
        if isinstance(extra_fields, dict) and extra_fields:
            try:
                suffix = json.dumps(extra_fields, default=str)
            except Exception:
                suffix = "{}"
            return f"{base} | {suffix}"
        return base


def configure_logging(
    level: str = "INFO",
    log_format: str = "json",
    stream: Any = None,
    force: bool = True,
) -> None:
    """Configure the root logger once (idempotent unless force=True)."""
    normalized_level = level.upper().strip()
    if normalized_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        normalized_level = "INFO"
    handler = logging.StreamHandler(stream or sys.stdout)
    if log_format == "text":
        handler.setFormatter(_TextFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    else:
        handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    if force:
        root.handlers.clear()
    if not root.handlers:
        root.addHandler(handler)
    root.setLevel(getattr(logging, normalized_level))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


__all__ = ["configure_logging", "get_logger"]
