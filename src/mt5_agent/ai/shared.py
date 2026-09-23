"""Shared helpers: timing, JSON decoding, usage extraction."""

from __future__ import annotations

import json
import time
from typing import Any

from mt5_agent.ai.errors import LLMParseError, LLMProviderError, LLMTimeoutError
from mt5_agent.ai.http import HttpClient, HttpResponse


class Stopwatch:
    """Monotonic timer returning elapsed milliseconds."""

    def __init__(self) -> None:
        self._start = time.monotonic()

    def elapsed_ms(self) -> float:
        return (time.monotonic() - self._start) * 1000.0


def decode_body(response: HttpResponse, *, provider: str, url: str) -> Any:
    """Decode an HTTP body as JSON; maps transport failures to `LLMError`s."""
    if response.status < 200 or response.status >= 300:
        raise LLMProviderError(
            f"HTTP {response.status} from {url}",
            provider=provider,
            status=response.status,
        )
    try:
        return json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LLMParseError(
            f"Invalid JSON from {provider}: {exc}",
            provider=provider,
            raw=response.body[:500].decode("utf-8", "replace"),
        ) from exc


def parse_structured(text: str, *, provider: str) -> Any:
    """Parse `text` as JSON for `response_format='json'` requests."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMParseError(
            f"Response is not valid JSON ({exc}); raw kept in `raw`.",
            provider=provider,
            raw=text[:2000],
        ) from exc


def post_json(
    http: HttpClient,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_s: float,
    provider: str,
) -> tuple[Any, float]:
    """POST + decode, returning `(data, latency_ms)`."""
    timer = Stopwatch()
    try:
        response = http.post(url, headers=headers, payload=payload, timeout_s=timeout_s)
    except TimeoutError as exc:
        raise LLMTimeoutError(f"{provider} timed out after {timeout_s}s") from exc
    latency_ms = timer.elapsed_ms()
    return decode_body(response, provider=provider, url=url), latency_ms


__all__ = ["Stopwatch", "decode_body", "parse_structured", "post_json"]
