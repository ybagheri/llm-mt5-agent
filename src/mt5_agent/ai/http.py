"""Minimal HTTP transport (stdlib only) behind an injectable protocol.

Adapters depend on `HttpClient`, never on a concrete HTTP library, so unit
tests inject fakes and no new runtime dependencies are required. Timeouts are
enforced per call; transport errors surface as `LLMTimeoutError` /
`LLMProviderError` via `raise_for_status`-style mapping in adapters.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from mt5_agent.ai.errors import LLMProviderError, LLMTimeoutError


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: bytes
    headers: dict[str, str]


class HttpClient(Protocol):
    """Injectable HTTP POST transport."""

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_s: float,
    ) -> HttpResponse: ...


class UrllibHttpClient:
    """Stdlib `urllib` implementation of `HttpClient`."""

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_s: float,
    ) -> HttpResponse:
        data = json.dumps(payload).encode("utf-8")
        merged = {"Content-Type": "application/json", **headers}
        request = urllib.request.Request(  # noqa: S310 (URL from explicit provider config)
            url, data=data, headers=merged, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
                status = int(response.status)
                body = response.read()
                response_headers = {k.lower(): v for k, v in response.headers.items()}
                return HttpResponse(status, body, response_headers)
        except TimeoutError as exc:
            raise LLMTimeoutError(f"HTTP timeout after {timeout_s}s: {url}") from exc
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read()
            except Exception:
                body = b""
            raise LLMProviderError(
                f"HTTP {exc.code} from {url}: {body[:500]!r}",
                status=int(exc.code),
            ) from exc
        except urllib.error.URLError as exc:
            reason = str(exc.reason)
            if "timed out" in reason.lower():
                raise LLMTimeoutError(f"HTTP timeout: {url} ({reason})") from exc
            raise LLMProviderError(f"HTTP transport error for {url}: {reason}") from exc
        except OSError as exc:
            raise LLMProviderError(f"HTTP transport error for {url}: {exc}") from exc


__all__ = ["HttpClient", "HttpResponse", "UrllibHttpClient"]
