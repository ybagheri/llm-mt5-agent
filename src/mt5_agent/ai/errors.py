"""LLM errors (no provider SDK imports)."""

from __future__ import annotations


class LLMError(Exception):
    """Base class for all LLM-layer errors."""


class LLMConfigurationError(LLMError):
    """Raised for missing/invalid provider configuration (no key, unknown provider)."""


class LLMProviderError(LLMError):
    """Raised when the provider returns an error (HTTP/API-level failure)."""

    def __init__(self, message: str, *, provider: str = "", status: int | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.status = status


class LLMTimeoutError(LLMProviderError):
    """Raised when a provider call exceeds the configured timeout."""


class LLMParseError(LLMError):
    """Raised when a response (esp. structured/JSON) cannot be decoded."""

    def __init__(self, message: str, *, provider: str = "", raw: str = "") -> None:
        super().__init__(message)
        self.provider = provider
        self.raw = raw


__all__ = [
    "LLMConfigurationError",
    "LLMError",
    "LLMParseError",
    "LLMProviderError",
    "LLMTimeoutError",
]
