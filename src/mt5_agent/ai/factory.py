"""Provider factory: configuration -> `LLMProvider` (no hard-coded selection).

Selection is data-driven (`llm_provider` + model + key + base URL); adding a
new vendor means registering a preset here, never branching in callers.
"""

from __future__ import annotations

from typing import Any

from mt5_agent.ai.errors import LLMConfigurationError
from mt5_agent.ai.gemini import GeminiProvider
from mt5_agent.ai.http import HttpClient
from mt5_agent.ai.openai_compat import OpenAICompatibleProvider
from mt5_agent.ai.provider import LLMProvider

SUPPORTED_PROVIDERS = ("none", "openai", "deepseek", "gemini", "ollama")

_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "deepseek": "deepseek-chat",
    "gemini": "gemini-2.0-flash",
    "ollama": "llama3.1",
}

_DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "ollama": "http://localhost:11434/v1",
}


def create_provider(
    provider: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_s: float = 30.0,
    http: HttpClient | None = None,
) -> LLMProvider:
    """Build the configured provider. Raises `LLMConfigurationError` when unusable."""
    name = (provider or "").strip().lower()
    if name == "none" or not name:
        raise LLMConfigurationError(
            "LLM provider is 'none'. Set MT5_AGENT_LLM_PROVIDER to one of: "
            "openai, deepseek, gemini, ollama."
        )
    if name == "gemini":
        return GeminiProvider(
            api_key=api_key or "",
            model=(model or _default_model(name)).strip(),
            timeout_s=timeout_s,
            base_url=(base_url or "https://generativelanguage.googleapis.com/v1beta"),
            http=http,
        )
    if name in ("openai", "deepseek", "ollama"):
        resolved_model = (model or _default_model(name) or "").strip()
        if name in ("openai", "deepseek") and not (api_key or "").strip():
            raise LLMConfigurationError(f"{name}: api key is required")
        return OpenAICompatibleProvider(
            provider_name=name,
            base_url=base_url or _DEFAULT_BASE_URLS[name],
            api_key=api_key,
            model=resolved_model,
            timeout_s=timeout_s,
            http=http,
        )
    raise LLMConfigurationError(
        f"Unknown LLM provider: {provider!r}. Supported: {', '.join(SUPPORTED_PROVIDERS)}."
    )


def provider_from_settings(settings: Any, *, http: HttpClient | None = None) -> LLMProvider:
    """Build a provider from `AppSettings` (key passed through, never logged)."""
    return create_provider(
        str(getattr(settings, "llm_provider", "none")),
        model=getattr(settings, "llm_model", None),
        api_key=getattr(settings, "llm_api_key", None),
        base_url=getattr(settings, "llm_base_url", None),
        timeout_s=float(getattr(settings, "llm_timeout_s", 30.0)),
        http=http,
    )


def _default_model(name: str) -> str:
    return _DEFAULT_MODELS.get(name, "")


__all__ = ["SUPPORTED_PROVIDERS", "create_provider", "provider_from_settings"]
