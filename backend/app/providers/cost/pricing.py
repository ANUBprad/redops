"""Pricing model.

Defines immutable pricing tiers for provider model billing.
Supports input, output, cached, image, audio, batch, and
streaming pricing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class PricingTier:
    """Pricing for a specific billing dimension.

    Prices are in USD per 1,000 tokens (or per unit for
    non-token pricing like images or audio seconds).
    """

    name: str
    price_per_unit: float
    unit: str = "per_1k_tokens"
    min_quantity: int = 0
    max_quantity: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def calculate(self, quantity: int) -> float:
        """Calculate cost for the given quantity.

        Args:
            quantity: Number of units consumed.

        Returns:
            Cost in USD.

        """
        return (quantity / 1000.0) * self.price_per_unit


@dataclass(frozen=True, slots=True)
class PricingModel:
    """Complete pricing model for a provider model.

    Contains all pricing tiers covering the various billing
    dimensions for model usage.
    """

    model_id: str
    provider_name: str
    input_tier: PricingTier
    output_tier: PricingTier
    cached_tier: PricingTier | None = None
    image_tier: PricingTier | None = None
    audio_tier: PricingTier | None = None
    batch_input_tier: PricingTier | None = None
    batch_output_tier: PricingTier | None = None
    streaming_tier: PricingTier | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def calculate_input_cost(self, tokens: int) -> float:
        """Calculate input token cost."""
        return self.input_tier.calculate(tokens)

    def calculate_output_cost(self, tokens: int) -> float:
        """Calculate output token cost."""
        return self.output_tier.calculate(tokens)

    def calculate_cached_cost(self, tokens: int) -> float:
        """Calculate cached token cost.

        Falls back to input pricing if no cached tier exists.
        """
        tier = self.cached_tier or self.input_tier
        return tier.calculate(tokens)

    def calculate_image_cost(self, count: int) -> float:
        """Calculate image processing cost.

        Returns 0.0 if no image pricing tier exists.
        """
        if self.image_tier is None:
            return 0.0
        return self.image_tier.calculate(count)

    def calculate_audio_cost(self, units: int) -> float:
        """Calculate audio processing cost.

        Returns 0.0 if no audio pricing tier exists.
        """
        if self.audio_tier is None:
            return 0.0
        return self.audio_tier.calculate(units)

    def calculate_batch_input_cost(self, tokens: int) -> float:
        """Calculate batch input cost.

        Falls back to standard input pricing.
        """
        tier = self.batch_input_tier or self.input_tier
        return tier.calculate(tokens)

    def calculate_batch_output_cost(self, tokens: int) -> float:
        """Calculate batch output cost.

        Falls back to standard output pricing.
        """
        tier = self.batch_output_tier or self.output_tier
        return tier.calculate(tokens)

    def calculate_streaming_cost(self, tokens: int) -> float:
        """Calculate streaming cost.

        Falls back to standard output pricing.
        """
        tier = self.streaming_tier or self.output_tier
        return tier.calculate(tokens)
