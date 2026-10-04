"""Cost estimation helpers (configurable rates)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelRateCard:
    """USD per 1M tokens."""

    input_per_million: float
    output_per_million: float


# Conservative defaults until live billing APIs are wired.
DEFAULT_RATES: dict[str, ModelRateCard] = {
    "z-ai/glm-5.2": ModelRateCard(input_per_million=0.50, output_per_million=1.50),
    "DeepSeek-V4-Flash-0731": ModelRateCard(input_per_million=0.10, output_per_million=0.40),
}


def estimate_cost_usd(
    model: str,
    *,
    prompt_tokens: int,
    completion_tokens: int,
    rates: dict[str, ModelRateCard] | None = None,
) -> float:
    card = (rates or DEFAULT_RATES).get(model)
    if card is None:
        card = ModelRateCard(input_per_million=1.0, output_per_million=3.0)
    input_cost = (prompt_tokens / 1_000_000.0) * card.input_per_million
    output_cost = (completion_tokens / 1_000_000.0) * card.output_per_million
    return round(input_cost + output_cost, 8)
