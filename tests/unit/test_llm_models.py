"""LLM model tests (validation only, no network)."""

from __future__ import annotations

import pytest

from mt5_agent.ai.models import LLMMessage, LLMRequest


def test_message_roles() -> None:
    assert LLMMessage("user", "hi").role == "user"
    with pytest.raises(ValueError):
        LLMMessage("tool", "hi")
    with pytest.raises(ValueError):
        LLMMessage("user", "   ")


def test_request_validation() -> None:
    with pytest.raises(ValueError):
        LLMRequest(messages=())
    with pytest.raises(ValueError):
        LLMRequest((LLMMessage("user", "hi"),), response_format="xml")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        LLMRequest((LLMMessage("user", "hi"),), temperature=5.0)
    req = LLMRequest(
        (
            LLMMessage("system", "sys"),
            LLMMessage("user", "hi"),
        )
    )
    assert req.system_prompt == "sys"
    assert LLMRequest((LLMMessage("user", "hi"),)).system_prompt is None
