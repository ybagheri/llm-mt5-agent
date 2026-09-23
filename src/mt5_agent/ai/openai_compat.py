"""OpenAI-compatible chat-completions provider (OpenAI, DeepSeek, Ollama).

All three vendors speak the `/chat/completions` schema; only base URL, auth,
and default model differ. One adapter, three factory presets — no per-vendor
code duplication, no SDK dependencies.
"""

from __future__ import annotations

from typing import Any

from mt5_agent.ai.errors import LLMConfigurationError, LLMParseError, LLMProviderError
from mt5_agent.ai.http import HttpClient, UrllibHttpClient
from mt5_agent.ai.models import LLMRequest, LLMResponse, LLMUsage
from mt5_agent.ai.provider import LLMProvider
from mt5_agent.ai.shared import parse_structured, post_json


class OpenAICompatibleProvider(LLMProvider):
    """`/v1/chat/completions`-style provider (OpenAI / DeepSeek / Ollama)."""

    def __init__(
        self,
        *,
        provider_name: str,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout_s: float = 30.0,
        http: HttpClient | None = None,
    ) -> None:
        if not model.strip():
            raise LLMConfigurationError(f"{provider_name}: model must be non-empty")
        if timeout_s < 1.0 or timeout_s > 300.0:
            raise LLMConfigurationError("timeout_s must be 1..300")
        self._provider_name = provider_name
        self.name = provider_name
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._http = http or UrllibHttpClient()

    @property
    def model(self) -> str:
        return self._model

    def generate(self, request: LLMRequest) -> LLMResponse:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        payload["temperature"] = request.temperature
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        data, latency_ms = post_json(
            self._http,
            self._url,
            headers=headers,
            payload=payload,
            timeout_s=self._timeout_s,
            provider=self._provider_name,
        )
        return self._to_response(data, request, latency_ms)

    def _to_response(self, data: Any, request: LLMRequest, latency_ms: float) -> LLMResponse:
        if not isinstance(data, dict):
            raise LLMParseError(
                f"Unexpected {self._provider_name} envelope: {type(data).__name__}",
                provider=self._provider_name,
            )
        if "error" in data and isinstance(data["error"], dict):
            message = str(data["error"].get("message", data["error"]))
            raise LLMProviderError(
                f"{self._provider_name} error: {message}", provider=self._provider_name
            )
        try:
            choices = data["choices"]
            message = choices[0]["message"]
            text = message.get("content") or ""
            finish = str(choices[0].get("finish_reason", ""))
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise LLMParseError(
                f"Unexpected {self._provider_name} envelope: {exc}",
                provider=self._provider_name,
            ) from exc
        if not isinstance(text, str) or not text.strip():
            # Some providers return content parts; flatten best-effort.
            text = _flatten_content(message.get("content"))
        if not text.strip():
            raise LLMParseError(
                f"{self._provider_name} returned empty content.",
                provider=self._provider_name,
            )
        usage = _usage_of(data.get("usage"))
        structured = (
            parse_structured(text, provider=self._provider_name)
            if request.response_format == "json"
            else None
        )
        return LLMResponse(
            text=text,
            provider=self._provider_name,
            model=self._model,
            latency_ms=latency_ms,
            usage=usage,
            structured=structured,
            finish_reason=finish,
            raw=data if isinstance(data, dict) else {},
        )


def _flatten_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts)
    return ""


def _usage_of(raw: Any) -> LLMUsage:
    if not isinstance(raw, dict):
        return LLMUsage()

    def _int(key: str) -> int | None:
        value = raw.get(key)
        return int(value) if isinstance(value, (int, float)) and value >= 0 else None

    return LLMUsage(
        prompt_tokens=_int("prompt_tokens"),
        completion_tokens=_int("completion_tokens"),
        total_tokens=_int("total_tokens"),
    )


__all__ = ["OpenAICompatibleProvider"]
