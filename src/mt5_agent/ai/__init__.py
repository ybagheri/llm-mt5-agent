"""AI layer: provider-agnostic LLM access (no SDK dependencies)."""

from __future__ import annotations

from mt5_agent.ai.errors import (
    LLMConfigurationError,
    LLMError,
    LLMParseError,
    LLMProviderError,
    LLMTimeoutError,
)
from mt5_agent.ai.factory import (
    SUPPORTED_PROVIDERS,
    create_provider,
    provider_from_settings,
)
from mt5_agent.ai.gemini import GeminiProvider
from mt5_agent.ai.http import HttpClient, HttpResponse, UrllibHttpClient
from mt5_agent.ai.models import LLMMessage, LLMRequest, LLMResponse, LLMUsage
from mt5_agent.ai.openai_compat import OpenAICompatibleProvider
from mt5_agent.ai.provider import LLMProvider

__all__ = [
    "SUPPORTED_PROVIDERS",
    "GeminiProvider",
    "HttpClient",
    "HttpResponse",
    "LLMConfigurationError",
    "LLMError",
    "LLMMessage",
    "LLMParseError",
    "LLMProvider",
    "LLMProviderError",
    "LLMRequest",
    "LLMResponse",
    "LLMTimeoutError",
    "LLMUsage",
    "OpenAICompatibleProvider",
    "UrllibHttpClient",
    "create_provider",
    "provider_from_settings",
]
