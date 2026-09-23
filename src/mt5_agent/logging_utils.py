"""Structured logging: JSON (default) or human-readable text.

Usage:
    from mt5_agent.logging_utils import configure_logging, get_logger
    configure_logging(level="INFO", log_format="json")
    logger = get_logger(__name__)
    logger.info("market snapshot", extra={"extra_fields": {"symbol": "EURUSD"}})

Rules:
  - Never log secrets (passwords, API keys, tokens). Callers must not put them
    in messages or `extra_fields`.
  - `configure_logging()` installs a scrubbing filter that redacts secret-like
    values as a second line of defense (defense in depth, not a license to
    log secrets).
  - `extra_fields` dict in `extra` is merged into the JSON record.
  - `audit()` emits structured audit events (`audit_event` field) used for
    post-incident reconstruction (see docs/operations/hardening.md).
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

_MASK = "***"

# Keys whose values must never appear in logs (case-insensitive substring match).
_SECRET_KEY_PARTS = (
    "password",
    "passwd",
    "api_key",
    "apikey",
    "secret",
    "token",
    "authorization",
    "bearer",
    "private_key",
    "credentials",
)

# Inline `key=value` / `key: value` pairs and `Bearer <...>` tokens in free text.
_INLINE_PATTERNS = (
    re.compile(r"(?i)\b(api_key|password|passwd|secret|token)\b\s*[:=]\s*([^\s,}]+)"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-~+/=]+"),
)


def scrub_value(value: Any) -> Any:
    """Return a copy of `value` with secret-like entries replaced by `***`."""
    if isinstance(value, dict):
        return {
            key: (_MASK if _is_secret_key(key) else scrub_value(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        scrubbed = [scrub_value(item) for item in value]
        return type(value)(scrubbed) if isinstance(value, tuple) else scrubbed
    if isinstance(value, str):
        return scrub_message(value)
    return value


def scrub_message(message: str) -> str:
    """Redact inline secrets from a free-text log message."""
    redacted = message
    redacted = _INLINE_PATTERNS[0].sub(r"\1=***", redacted)
    redacted = _INLINE_PATTERNS[1].sub("Bearer ***", redacted)
    return redacted


def _is_secret_key(key: Any) -> bool:
    lowered = str(key).lower()
    return any(part in lowered for part in _SECRET_KEY_PARTS)


class SecretScrubbingFilter(logging.Filter):
    """Defense-in-depth filter: redacts secrets from records before emission."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = scrub_message(record.msg)
        if record.args:
            record.args = scrub_value(record.args)
        extra_fields = getattr(record, "extra_fields", None)
        if isinstance(extra_fields, dict):
            record.extra_fields = scrub_value(extra_fields)
        return True


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
    handler.addFilter(SecretScrubbingFilter())
    root = logging.getLogger()
    if force:
        root.handlers.clear()
    if not root.handlers:
        root.addHandler(handler)
    root.setLevel(getattr(logging, normalized_level))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def audit(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit a structured audit event (secrets are scrubbed before emission).

    `event` is a stable snake_case name (e.g. `order_submitted`); `fields`
    carry reconstruction context (cycle id, symbol, ticket, reason, ...).
    """
    logger.info(
        event,
        extra={
            "extra_fields": {
                "audit_event": event,
                "ts": datetime.now(UTC).isoformat(),
                **scrub_value(fields),
            }
        },
    )


__all__ = [
    "SecretScrubbingFilter",
    "audit",
    "configure_logging",
    "get_logger",
    "scrub_message",
    "scrub_value",
]
