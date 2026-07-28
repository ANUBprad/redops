"""Tests for cost framework."""

from __future__ import annotations

import pytest

from app.providers.cost.calculator import CostCalculator
from app.providers.cost.pricing import PricingModel, PricingTier
from app.providers.tokenization.usage import TokenUsage


def _make_pricing() -> PricingModel:
    return PricingModel(
        model_id="test-model",
        provider_name="test",
        input_tier=PricingTier(name="input", price_per_unit=10.0),
        output_tier=PricingTier(name="output", price_per_unit=30.0),
        cached_tier=PricingTier(name="cached", price_per_unit=1.0),
    )


class TestPricingTier:
    """Tests for PricingTier."""

    def test_calculate(self) -> None:
        tier = PricingTier(name="input", price_per_unit=10.0)
        assert tier.calculate(1000) == 10.0

    def test_calculate_fractional(self) -> None:
        tier = PricingTier(name="input", price_per_unit=10.0)
        assert tier.calculate(500) == 5.0


class TestPricingModel:
    """Tests for PricingModel."""

    def test_input_cost(self) -> None:
        pm = _make_pricing()
        assert pm.calculate_input_cost(1000) == 10.0

    def test_output_cost(self) -> None:
        pm = _make_pricing()
        assert pm.calculate_output_cost(1000) == 30.0

    def test_cached_cost(self) -> None:
        pm = _make_pricing()
        assert pm.calculate_cached_cost(1000) == 1.0

    def test_cached_cost_fallback(self) -> None:
        pm = PricingModel(
            model_id="m",
            provider_name="p",
            input_tier=PricingTier(name="input", price_per_unit=10.0),
            output_tier=PricingTier(name="output", price_per_unit=30.0),
        )
        assert pm.calculate_cached_cost(1000) == 10.0

    def test_image_cost_none(self) -> None:
        pm = _make_pricing()
        assert pm.calculate_image_cost(10) == 0.0

    def test_image_cost_with_tier(self) -> None:
        pm = PricingModel(
            model_id="m",
            provider_name="p",
            input_tier=PricingTier(name="input", price_per_unit=10.0),
            output_tier=PricingTier(name="output", price_per_unit=30.0),
            image_tier=PricingTier(name="image", price_per_unit=5.0, unit="per_image"),
        )
        assert pm.calculate_image_cost(10) == 0.05


class TestCostCalculator:
    """Tests for CostCalculator."""

    def test_register_and_get(self) -> None:
        calc = CostCalculator()
        pm = _make_pricing()
        calc.register_pricing(pm)
        assert calc.get_pricing("test", "test-model") is pm

    def test_unregister(self) -> None:
        calc = CostCalculator()
        calc.register_pricing(_make_pricing())
        calc.unregister_pricing("test", "test-model")
        assert calc.get_pricing("test", "test-model") is None

    def test_estimate_cost(self) -> None:
        calc = CostCalculator()
        calc.register_pricing(_make_pricing())
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        cost = calc.estimate_cost("test", "test-model", usage)
        # Input: 1000/1000 * 10 = 10.0
        # Output: 500/1000 * 30 = 15.0
        # Total: 25.0
        assert cost == 25.0

    def test_estimate_cost_unknown_model(self) -> None:
        calc = CostCalculator()
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        with pytest.raises(KeyError):
            calc.estimate_cost("test", "unknown", usage)

    def test_list_pricing_models(self) -> None:
        calc = CostCalculator()
        calc.register_pricing(_make_pricing())
        models = calc.list_pricing_models()
        assert len(models) == 1
