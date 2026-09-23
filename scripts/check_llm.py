"""LLM probe: send a prompt, print text/usage/latency (never trades)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mt5_agent.ai.factory import provider_from_settings  # noqa: E402
from mt5_agent.ai.models import LLMMessage, LLMRequest  # noqa: E402
from mt5_agent.config.loader import load_settings  # noqa: E402
from mt5_agent.logging_utils import configure_logging, get_logger  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe the configured LLM provider.")
    parser.add_argument("--prompt", default="Reply with exactly: ok")
    parser.add_argument("--system", default="You are a concise assistant.")
    parser.add_argument("--json", action="store_true", help="Request JSON output.")
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(level=settings.log_level, log_format=settings.log_format)
    logger = get_logger("check_llm")
    try:
        provider = provider_from_settings(settings)
    except Exception as exc:
        logger.warning("llm misconfigured", extra={"extra_fields": {"error": str(exc)}})
        print(json.dumps({"error": str(exc)}))
        return 2
    request = LLMRequest(
        (LLMMessage("system", args.system), LLMMessage("user", args.prompt)),
        response_format="json" if args.json else "text",
    )
    try:
        response = provider.generate(request)
    except Exception as exc:
        logger.warning("llm call failed", extra={"extra_fields": {"error": str(exc)}})
        print(json.dumps({"provider": settings.llm_provider, "error": str(exc)}))
        return 1
    print(
        json.dumps(
            {
                "provider": response.provider,
                "model": response.model,
                "latency_ms": round(response.latency_ms, 1),
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "finish_reason": response.finish_reason,
                "text": response.text,
                "structured": response.structured,
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
