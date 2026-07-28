"""Cost calculator.

Aggregates pricing models and computes estimated costs
for requests across providers and models.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.providers.cost.pricing import PricingModel  # noqa: TC001
from app.providers.tokenization.usage import TokenUsage  # noqa: TC001


@dataclass
class CostCalculator:
    """Calculates costs from pricing models and token usage.

    Maintains a registry of pricing models and provides
    cost estimation for individual requests and aggregations.
    """

    _pricing_models: dict[str, PricingModel] = field(default_factory=dict)

    def register_pricing(self, pricing: PricingModel) -> None:
        """Register a pricing model.

        Args:
            pricing: The pricing model to register.

        """
        key = f"{pricing.provider_name}:{pricing.model_id}"
        self._pricing_models[key] = pricing

    def unregister_pricing(self, provider_name: str, model_id: str) -> None:
        """Remove a pricing model.

        Args:
            provider_name: The provider name.
            model_id: The model identifier.

        """
        key = f"{provider_name}:{model_id}"
        self._pricing_models.pop(key, None)

    def get_pricing(self, provider_name: str, model_id: str) -> PricingModel | None:
        """Retrieve a pricing model.

        Args:
            provider_name: The provider name.
            model_id: The model identifier.

        Returns:
            The pricing model, or None if not registered.

        """
        key = f"{provider_name}:{model_id}"
        return self._pricing_models.get(key)

    def estimate_cost(
        self,
        provider_name: str,
        model_id: str,
        usage: TokenUsage,
        *,
        is_streaming: bool = False,
        is_batch: bool = False,
    ) -> float:
        """Estimate cost for a request.

        Args:
            provider_name: The provider name.
            model_id: The model identifier.
            usage: Token usage for the request.
            is_streaming: Whether the request uses streaming.
            is_batch: Whether the request is a batch request.

        Returns:
            Estimated cost in USD.

        Raises:
            KeyError: If no pricing model is registered.

        """
        pricing = self.get_pricing(provider_name, model_id)
        if pricing is None:
            msg = f"No pricing model for {provider_name}:{model_id}"
            raise KeyError(msg)

        if is_batch:
            input_cost = pricing.calculate_batch_input_cost(usage.input_tokens)
            output_cost = pricing.calculate_batch_output_cost(usage.output_tokens)
        elif is_streaming:
            input_cost = pricing.calculate_input_cost(usage.input_tokens)
            output_cost = pricing.calculate_streaming_cost(usage.output_tokens)
        else:
            input_cost = pricing.calculate_input_cost(usage.input_tokens)
            output_cost = pricing.calculate_output_cost(usage.output_tokens)

        cached_cost = 0.0
        if usage.cached_tokens > 0 and pricing.cached_tier is not None:
            cached_cost = pricing.calculate_cached_cost(usage.cached_tokens)

        image_cost = pricing.calculate_image_cost(0)
        audio_cost = pricing.calculate_audio_cost(usage.audio_tokens)

        return input_cost + output_cost - cached_cost + image_cost + audio_cost

    def list_pricing_models(self) -> list[PricingModel]:
        """Return all registered pricing models."""
        return list(self._pricing_models.values())
