from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    input_per_million: float
    output_per_million: float


MODEL_PRICING: dict[str, ModelPricing] = {
    "gemini-2.5-flash": ModelPricing(
        input_per_million=0.30,
        output_per_million=2.50,
    ),
    "gemini-2.5-flash-lite": ModelPricing(
        input_per_million=0.10,
        output_per_million=0.40,
    ),
}


def estimate_cost_usd(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    thinking_tokens: int = 0,
) -> float:
    """
    Estimate Gemini token cost in USD.

    Thinking tokens are billed as output tokens for
    Gemini thinking models.
    """

    pricing = MODEL_PRICING.get(model)

    if pricing is None:
        return 0.0

    billable_output_tokens = output_tokens + thinking_tokens

    input_cost = input_tokens / 1_000_000 * pricing.input_per_million

    output_cost = billable_output_tokens / 1_000_000 * pricing.output_per_million

    return input_cost + output_cost
