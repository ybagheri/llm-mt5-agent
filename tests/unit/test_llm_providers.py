"""LLM adapter tests (fake HTTP transport, no network, no SDKs)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from mt5_agent.ai.errors import (
    LLMConfigurationError,
    LLMParseError,
    LLMProviderError,
)
from mt5_agent.ai.factory import SUPPORTED_PROVIDERS, create_provider, provider_from_settings
from mt5_agent.ai.gemini import GeminiProvider
from mt5_agent.ai.http import HttpResponse
from mt5_agent.ai.models import LLMMessage, LLMRequest, LLMUsage
from mt5_agent.ai.openai_compat import OpenAICompatibleProvider
from mt5_agent.config.settings import AppSettings


class FakeHttp:
    """Canned-transport double capturing requests."""

    def __init__(self, payload: Any, status: int = 200) -> None:
        self.payload = payload
        self.status = status
        self.calls: list[dict[str, Any]] = []

    def post(
        self, url: str, *, headers: dict[str, str], payload: dict[str, Any], timeout_s: float
    ) -> HttpResponse:
        self.calls.append({"url": url, "headers": headers, "payload": payload})
        body = (
            json.dumps(self.payload).encode()
            if not isinstance(self.payload, bytes)
            else self.payload
        )
        return HttpResponse(self.status, body, {})


def _openai_ok(text: str = "hello", **usage: int) -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8} | usage,
        "model": "m",
    }


def _gemini_ok(text: str = "hi") -> dict[str, Any]:
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 2, "totalTokenCount": 6},
    }


def _req(fmt: str = "text") -> LLMRequest:
    return LLMRequest((LLMMessage("user", "ping"),), response_format=fmt)  # type: ignore[arg-type]


def test_openai_text_and_usage() -> None:
    http = FakeHttp(_openai_ok())
    provider = OpenAICompatibleProvider(
        provider_name="openai", base_url="https://x/v1", api_key="k", model="m", http=http
    )
    response = provider.generate(_req())
    assert response.text == "hello"
    assert response.usage == LLMUsage(5, 3, 8)
    assert response.latency_ms >= 0
    assert response.provider == "openai"
    assert http.calls[0]["headers"]["Authorization"] == "Bearer k"


def test_openai_structured_json() -> None:
    http = FakeHttp(_openai_ok('{"a": 1}'))
    provider = OpenAICompatibleProvider(
        provider_name="deepseek", base_url="https://x", api_key="k", model="m", http=http
    )
    response = provider.generate(_req("json"))
    assert response.structured == {"a": 1}
    assert http.calls[0]["payload"]["response_format"] == {"type": "json_object"}


def test_openai_bad_json_raises_parse() -> None:
    http = FakeHttp(_openai_ok("not json"))
    provider = OpenAICompatibleProvider(
        provider_name="openai", base_url="https://x", api_key="k", model="m", http=http
    )
    with pytest.raises(LLMParseError):
        provider.generate(_req("json"))


def test_openai_api_error_envelope() -> None:
    http = FakeHttp({"error": {"message": "bad key"}})
    provider = OpenAICompatibleProvider(
        provider_name="openai", base_url="https://x", api_key="k", model="m", http=http
    )
    with pytest.raises(LLMProviderError, match="bad key"):
        provider.generate(_req())


def test_openai_http_status_error() -> None:
    http = FakeHttp({"oops": True}, status=500)
    provider = OpenAICompatibleProvider(
        provider_name="openai", base_url="https://x", api_key="k", model="m", http=http
    )
    with pytest.raises(LLMProviderError):
        provider.generate(_req())


def test_openai_empty_content_raises() -> None:
    http = FakeHttp({"choices": [{"message": {"content": "  "}, "finish_reason": "stop"}]})
    provider = OpenAICompatibleProvider(
        provider_name="openai", base_url="https://x", api_key="k", model="m", http=http
    )
    with pytest.raises(LLMParseError):
        provider.generate(_req())


def test_ollama_no_key_ok() -> None:
    http = FakeHttp(_openai_ok("local"))
    provider = OpenAICompatibleProvider(
        provider_name="ollama",
        base_url="http://localhost:11434/v1",
        api_key=None,
        model="llama3.1",
        http=http,
    )
    assert provider.generate(_req()).text == "local"
    assert "Authorization" not in http.calls[0]["headers"]


def test_gemini_generate() -> None:
    http = FakeHttp(_gemini_ok("yo"))
    provider = GeminiProvider(api_key="k", model="gemini-2.0-flash", http=http)
    request = LLMRequest(
        (
            LLMMessage("system", "be brief"),
            LLMMessage("user", "hi"),
        )
    )
    response = provider.generate(request)
    assert response.text == "yo"
    assert response.usage.total_tokens == 6
    assert http.calls[0]["headers"]["x-goog-api-key"] == "k"
    assert "generateContent" in http.calls[0]["url"]


def test_gemini_structured() -> None:
    http = FakeHttp(_gemini_ok('{"ok": true}'))
    provider = GeminiProvider(api_key="k", model="m", http=http)
    assert provider.generate(_req("json")).structured == {"ok": True}


def test_gemini_requires_key() -> None:
    with pytest.raises(LLMConfigurationError):
        GeminiProvider(api_key="", model="m")


def test_factory_selection() -> None:
    assert "ollama" in SUPPORTED_PROVIDERS
    assert (
        create_provider("openai", api_key="k", model="m", http=FakeHttp(_openai_ok())).name
        == "openai"
    )
    assert (
        create_provider("deepseek", api_key="k", http=FakeHttp(_openai_ok())).model
        == "deepseek-chat"
    )
    assert create_provider("ollama", http=FakeHttp(_openai_ok())).name == "ollama"
    assert (
        create_provider("gemini", api_key="k", model="m", http=FakeHttp(_gemini_ok())).name
        == "gemini"
    )


def test_factory_rejects() -> None:
    with pytest.raises(LLMConfigurationError):
        create_provider("none")
    with pytest.raises(LLMConfigurationError):
        create_provider("wat")
    with pytest.raises(LLMConfigurationError):
        create_provider("openai", api_key="", model="m", http=FakeHttp({}))
    with pytest.raises(LLMConfigurationError):
        create_provider("openai", api_key="k", model="  ", http=FakeHttp({}))


def test_factory_from_settings() -> None:
    settings = AppSettings(llm_provider="ollama", llm_model="qwen")
    provider = provider_from_settings(settings, http=FakeHttp(_openai_ok("s")))
    assert provider.name == "ollama"
    assert provider.model == "qwen"


def test_settings_mask_redacts_key() -> None:
    settings = AppSettings(llm_provider="openai", llm_api_key="super-secret")
    assert settings.masked()["llm_api_key"] == "***"
    assert "super-secret" not in str(settings.masked())
