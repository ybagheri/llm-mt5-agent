"""LLM cost estimator (static per-model table; estimates, not bills)."""

from __future__ import annotations

# USD per 1M tokens (input, output). Public list prices, snapshot 2026-09.
# Unknown models -> None (dashboard shows "n/a", never a fabricated number).
_MODEL_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "deepseek-chat": (0.27, 1.10),
    "gemini-2.0-flash": (0.10, 0.40),
    "llama3.1": (0.0, 0.0),
    "qwen": (0.0, 0.0),
}


def estimate_cost_usd(
    model: str, prompt_tokens: int | None, completion_tokens: int | None
) -> float | None:
    """Estimate cost or None when model/tokens are unknown (never invent)."""
    prices = _MODEL_PRICES.get((model or "").strip().lower())
    if prices is None or prompt_tokens is None or completion_tokens is None:
        return None
    input_price, output_price = prices
    return round(
        prompt_tokens / 1_000_000 * input_price + completion_tokens / 1_000_000 * output_price, 6
    )


__all__ = ["estimate_cost_usd"]
