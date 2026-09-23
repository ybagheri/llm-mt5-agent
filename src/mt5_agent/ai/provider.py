"""LLM provider interface (strategy/Planner code against this, never SDKs)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from mt5_agent.ai.models import LLMRequest, LLMResponse


class LLMProvider(ABC):
    """Abstract text/JSON generation provider."""

    name: str = "provider"

    @property
    @abstractmethod
    def model(self) -> str:
        """Active model identifier."""
        ...

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate once; raises `LLMError` subclasses on failure."""
        ...

    def close(self) -> None:
        """Release resources (default: no-op; idempotent)."""
        return None


__all__ = ["LLMProvider"]
