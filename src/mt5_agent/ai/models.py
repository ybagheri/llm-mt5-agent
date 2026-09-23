"""LLM request/response models (provider-agnostic, no SDK deps)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ResponseFormat = Literal["text", "json"]


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """Single chat message."""

    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in ("system", "user", "assistant"):
            raise ValueError(f"invalid role: {self.role!r}")
        if not self.content.strip():
            raise ValueError("content must be non-empty")


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """Provider-agnostic generation request."""

    messages: tuple[LLMMessage, ...]
    response_format: ResponseFormat = "text"
    max_tokens: int | None = None
    temperature: float = 0.2
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("at least one message is required")
        if self.response_format not in ("text", "json"):
            raise ValueError("response_format must be 'text' or 'json'")
        if self.max_tokens is not None and self.max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be 0..2")

    @property
    def system_prompt(self) -> str | None:
        for message in self.messages:
            if message.role == "system":
                return message.content
        return None


@dataclass(frozen=True, slots=True)
class LLMUsage:
    """Token usage when reported by the provider (all optional)."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Provider-agnostic generation result with observability metadata."""

    text: str
    provider: str
    model: str
    latency_ms: float
    usage: LLMUsage = field(default_factory=LLMUsage)
    structured: Any | None = None
    finish_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


__all__ = ["LLMMessage", "LLMRequest", "LLMResponse", "LLMUsage", "ResponseFormat"]
