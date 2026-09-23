"""Live LLM integration test (opt-in; spends no trades, may spend tokens).

Run with: MT5_AGENT_RUN_LIVE_LLM_TESTS=true MT5_AGENT_LLM_API_KEY=... \
  pytest tests/integration/test_llm_live.py -q
"""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("MT5_AGENT_RUN_LIVE_LLM_TESTS", "false").lower() != "true",
        reason="live LLM not requested",
    ),
]


def test_live_llm_generate() -> None:
    from mt5_agent.ai.factory import provider_from_settings
    from mt5_agent.ai.models import LLMMessage, LLMRequest
    from mt5_agent.config.loader import load_settings

    settings = load_settings()
    if settings.llm_provider in ("none", ""):
        pytest.skip("no LLM provider configured")
    try:
        provider = provider_from_settings(settings)
    except Exception as exc:
        pytest.skip(f"LLM misconfigured: {exc}")
        return
    request = LLMRequest((LLMMessage("user", "Reply with exactly: ok"),))
    try:
        response = provider.generate(request)
    except Exception as exc:
        pytest.skip(f"LLM unavailable: {exc}")
        return
    assert response.text.strip() != ""
    assert response.latency_ms >= 0
