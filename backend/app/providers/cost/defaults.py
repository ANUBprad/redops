"""Default pricing for common provider models.

Real per-token prices (USD per 1M tokens) for the models the
platform evaluates by default. Keeping them here means computed
costs reflect actual provider billing without external lookups.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NotRequired, TypedDict

from app.providers.cost.calculator import CostCalculator
from app.providers.cost.pricing import PricingModel, PricingTier

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "DEFAULT_PRICING",
    "build_default_cost_calculator",
    "register_default_pricing",
]


class _PricingEntry(TypedDict):
    """Row in the built-in pricing table."""

    model_id: str
    input_per_million: float
    output_per_million: float
    cached_input_per_million: NotRequired[float]


def _usd_per_1k(per_million: float) -> float:
    """Convert a per-1M price to the per-1K unit used by PricingTier.

    Args:
        per_million: Price in USD per one million tokens.

    Returns:
        Price in USD per one thousand tokens.

    """
    return per_million / 1000.0


def _tier(
    name: str,
    per_1k_price: float,
) -> PricingTier:
    """Build an input/output pricing tier.

    Args:
        name: Tier name.
        per_1k_price: Price in USD per 1K tokens.

    Returns:
        A PricingTier instance.

    """
    return PricingTier(name=name, price_per_unit=per_1k_price)


def _model(
    provider_name: str,
    model_id: str,
    *,
    input_per_million: float,
    output_per_million: float,
    cached_input_per_million: float | None = None,
) -> PricingModel:
    """Build a PricingModel for a model.

    Args:
        provider_name: Provider identifier (e.g. ``openai``).
        model_id: Model identifier.
        input_per_million: Input price in USD per 1M tokens.
        output_per_million: Output price in USD per 1M tokens.
        cached_input_per_million: Optional cached input price.

    Returns:
        A PricingModel instance.

    """
    input_price = _usd_per_1k(input_per_million)
    output_price = _usd_per_1k(output_per_million)
    cached_tier: PricingTier | None = None
    if cached_input_per_million is not None:
        cached_tier = _tier("cached_input", _usd_per_1k(cached_input_per_million))
    return PricingModel(
        model_id=model_id,
        provider_name=provider_name,
        input_tier=_tier("input", input_price),
        output_tier=_tier("output", output_price),
        cached_tier=cached_tier,
    )


# OpenAI pricing: https://openai.com/api/pricing
_OPENAI_PRICING: tuple[_PricingEntry, ...] = (
    {
        "model_id": "gpt-4o",
        "input_per_million": 2.50,
        "output_per_million": 10.00,
        "cached_input_per_million": 1.25,
    },
    {
        "model_id": "gpt-4o-mini",
        "input_per_million": 0.15,
        "output_per_million": 0.60,
        "cached_input_per_million": 0.075,
    },
    {
        "model_id": "gpt-4.1",
        "input_per_million": 2.00,
        "output_per_million": 8.00,
        "cached_input_per_million": 0.50,
    },
    {
        "model_id": "gpt-4.1-mini",
        "input_per_million": 0.40,
        "output_per_million": 1.60,
        "cached_input_per_million": 0.10,
    },
    {
        "model_id": "gpt-4.1-nano",
        "input_per_million": 0.10,
        "output_per_million": 0.40,
        "cached_input_per_million": 0.025,
    },
    {
        "model_id": "gpt-4",
        "input_per_million": 30.00,
        "output_per_million": 60.00,
    },
    {
        "model_id": "o1",
        "input_per_million": 15.00,
        "output_per_million": 60.00,
        "cached_input_per_million": 7.50,
    },
    {
        "model_id": "o3",
        "input_per_million": 2.00,
        "output_per_million": 8.00,
        "cached_input_per_million": 0.50,
    },
)

# Anthropic pricing: https://docs.anthropic.com/en/docs/about-claude/pricing
_ANTHROPIC_PRICING: tuple[_PricingEntry, ...] = (
    {
        "model_id": "claude-sonnet-4-20250514",
        "input_per_million": 3.00,
        "output_per_million": 15.00,
        "cached_input_per_million": 0.30,
    },
    {
        "model_id": "claude-sonnet-4-20250414",
        "input_per_million": 3.00,
        "output_per_million": 15.00,
        "cached_input_per_million": 0.30,
    },
    {
        "model_id": "claude-haiku-4-20250514",
        "input_per_million": 1.00,
        "output_per_million": 5.00,
        "cached_input_per_million": 0.10,
    },
    {
        "model_id": "claude-3-5-sonnet-20241022",
        "input_per_million": 3.00,
        "output_per_million": 15.00,
        "cached_input_per_million": 0.30,
    },
    {
        "model_id": "claude-3-5-haiku-20241022",
        "input_per_million": 0.80,
        "output_per_million": 4.00,
        "cached_input_per_million": 0.08,
    },
)

DEFAULT_PRICING: tuple[PricingModel, ...] = tuple(
    _model("openai", **entry) for entry in _OPENAI_PRICING
) + tuple(_model("anthropic", **entry) for entry in _ANTHROPIC_PRICING)


def register_default_pricing(
    calculator: CostCalculator,
    *,
    pricing: Iterable[PricingModel] | None = None,
) -> CostCalculator:
    """Register default pricing models on a cost calculator.

    Args:
        calculator: The calculator to populate.
        pricing: Optional pricing models to register; defaults to
            the built-in DEFAULT_PRICING table.

    Returns:
        The same calculator, for chaining.

    """
    for pricing_model in pricing if pricing is not None else DEFAULT_PRICING:
        calculator.register_pricing(pricing_model)
    return calculator


def build_default_cost_calculator() -> CostCalculator:
    """Return a CostCalculator pre-populated with default pricing.

    Returns:
        A CostCalculator with all default pricing registered.

    """
    calculator = CostCalculator()
    register_default_pricing(calculator)
    return calculator
