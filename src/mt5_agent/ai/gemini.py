"""Google Gemini provider via the `generateContent` REST API (no SDK)."""

from __future__ import annotations

from typing import Any

from mt5_agent.ai.errors import LLMConfigurationError, LLMParseError, LLMProviderError
from mt5_agent.ai.http import HttpClient, UrllibHttpClient
from mt5_agent.ai.models import LLMRequest, LLMResponse, LLMUsage
from mt5_agent.ai.provider import LLMProvider
from mt5_agent.ai.shared import parse_structured, post_json


class GeminiProvider(LLMProvider):
    """Gemini `v1beta/models/{model}:generateContent` adapter (API-key auth)."""

    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_s: float = 30.0,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        http: HttpClient | None = None,
    ) -> None:
        if not api_key:
            raise LLMConfigurationError("gemini: api key is required")
        if not model.strip():
            raise LLMConfigurationError("gemini: model must be non-empty")
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._url = f"{base_url.rstrip('/')}/models/{model}:generateContent"
        self._http = http or UrllibHttpClient()

    @property
    def model(self) -> str:
        return self._model

    def generate(self, request: LLMRequest) -> LLMResponse:
        system, contents = _to_contents(request)
        payload: dict[str, Any] = {"contents": contents}
        if system:
            payload["system_instruction"] = {"parts": [{"text": system}]}
        config: dict[str, Any] = {"temperature": request.temperature}
        if request.max_tokens is not None:
            config["maxOutputTokens"] = request.max_tokens
        if request.response_format == "json":
            config["response_mime_type"] = "application/json"
        payload["generationConfig"] = config

        data, latency_ms = post_json(
            self._http,
            self._url,
            headers={"x-goog-api-key": self._api_key},
            payload=payload,
            timeout_s=self._timeout_s,
            provider=self.name,
        )
        return self._to_response(data, request, latency_ms)

    def _to_response(self, data: Any, request: LLMRequest, latency_ms: float) -> LLMResponse:
        if not isinstance(data, dict):
            raise LLMParseError("Unexpected gemini envelope.", provider=self.name)
        if "error" in data and isinstance(data["error"], dict):
            raise LLMProviderError(
                f"gemini error: {data['error'].get('message', data['error'])}",
                provider=self.name,
            )
        try:
            candidates = data["candidates"]
            parts = candidates[0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
            finish = str(candidates[0].get("finishReason", ""))
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise LLMParseError(f"Unexpected gemini envelope: {exc}", provider=self.name) from exc
        if not text.strip():
            raise LLMParseError("gemini returned empty content.", provider=self.name)
        usage = _usage_of(data.get("usageMetadata"))
        structured = (
            parse_structured(text, provider=self.name)
            if request.response_format == "json"
            else None
        )
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self._model,
            latency_ms=latency_ms,
            usage=usage,
            structured=structured,
            finish_reason=finish,
            raw=data if isinstance(data, dict) else {},
        )


def _to_contents(request: LLMRequest) -> tuple[str, list[dict[str, Any]]]:
    system = ""
    contents: list[dict[str, Any]] = []
    for message in request.messages:
        if message.role == "system":
            system += message.content
            continue
        role = "model" if message.role == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": message.content}]})
    if not contents:
        raise LLMConfigurationError("gemini: at least one non-system message is required")
    return system, contents


def _usage_of(raw: Any) -> LLMUsage:
    if not isinstance(raw, dict):
        return LLMUsage()

    def _int(key: str) -> int | None:
        value = raw.get(key)
        return int(value) if isinstance(value, (int, float)) and value >= 0 else None

    return LLMUsage(
        prompt_tokens=_int("promptTokenCount"),
        completion_tokens=_int("candidatesTokenCount"),
        total_tokens=_int("totalTokenCount"),
    )


__all__ = ["GeminiProvider"]
