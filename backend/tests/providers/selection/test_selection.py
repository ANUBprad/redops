"""Tests for selection strategies."""

from __future__ import annotations

import pytest

from app.providers.capabilities.capability import Capability
from app.providers.capabilities.capability_set import CapabilitySet
from app.providers.catalog.model import ModelMetadata
from app.providers.health.provider_health import ProviderHealth
from app.providers.health.status import ProviderStatus
from app.providers.models.enums import ModelStatus
from app.providers.selection.capability import CapabilityMatchingStrategy
from app.providers.selection.cheapest import CheapestStrategy
from app.providers.selection.context import HighestContextStrategy
from app.providers.selection.fallback import FallbackChainStrategy
from app.providers.selection.fastest import FastestStrategy
from app.providers.selection.health import HealthBasedStrategy
from app.providers.selection.round_robin import RoundRobinStrategy
from app.providers.selection.weighted import WeightedStrategy


def _model(
    model_id: str = "m1",
    provider: str = "p1",
    input_price: float = 0.01,
    output_price: float = 0.02,
    context_window: int = 4096,
    latency_tier: str = "standard",
    capabilities: CapabilitySet | None = None,
    status: ModelStatus = ModelStatus.ACTIVE,
) -> ModelMetadata:
    return ModelMetadata(
        provider_name=provider,
        model_id=model_id,
        context_window=context_window,
        capabilities=capabilities or CapabilitySet.of(Capability.CHAT),
        input_price_per_1k=input_price,
        output_price_per_1k=output_price,
        latency_tier=latency_tier,
        status=status,
    )


class TestCheapestStrategy:
    def test_selects_cheapest(self) -> None:
        s = CheapestStrategy()
        candidates = [
            _model("expensive", input_price=0.1),
            _model("cheap", input_price=0.001),
        ]
        result = s.select(candidates)
        assert result is not None
        assert result.model_id == "cheap"

    def test_empty_candidates(self) -> None:
        assert CheapestStrategy().select([]) is None

    def test_excludes_deprecated(self) -> None:
        s = CheapestStrategy()
        candidates = [
            _model("deprecated", input_price=0.001, status=ModelStatus.DEPRECATED),
            _model("active", input_price=0.01),
        ]
        result = s.select(candidates)
        assert result is not None
        assert result.model_id == "active"


class TestFastestStrategy:
    def test_selects_fastest(self) -> None:
        s = FastestStrategy()
        candidates = [
            _model("slow", latency_tier="slow"),
            _model("fast", latency_tier="fast"),
        ]
        result = s.select(candidates)
        assert result is not None
        assert result.model_id == "fast"


class TestHighestContextStrategy:
    def test_selects_largest_context(self) -> None:
        s = HighestContextStrategy()
        candidates = [
            _model("small", context_window=4096),
            _model("large", context_window=200_000),
        ]
        result = s.select(candidates)
        assert result is not None
        assert result.model_id == "large"


class TestCapabilityMatchingStrategy:
    def test_selects_matching(self) -> None:
        required = CapabilitySet.of(Capability.CHAT, Capability.STREAMING)
        s = CapabilityMatchingStrategy(required)
        candidates = [
            _model("chat_only", capabilities=CapabilitySet.of(Capability.CHAT)),
            _model("full", capabilities=CapabilitySet.of(Capability.CHAT, Capability.STREAMING)),
        ]
        result = s.select(candidates)
        assert result is not None
        assert result.model_id == "full"

    def test_no_match(self) -> None:
        required = CapabilitySet.of(Capability.VISION)
        s = CapabilityMatchingStrategy(required)
        candidates = [_model("chat_only", capabilities=CapabilitySet.of(Capability.CHAT))]
        assert s.select(candidates) is None


class TestRoundRobinStrategy:
    def test_cycles_through(self) -> None:
        s = RoundRobinStrategy()
        candidates = [_model("a"), _model("b"), _model("c")]
        assert s.select(candidates).model_id == "a"
        assert s.select(candidates).model_id == "b"
        assert s.select(candidates).model_id == "c"
        assert s.select(candidates).model_id == "a"


class TestWeightedStrategy:
    def test_weighted_selection(self) -> None:
        s = WeightedStrategy(seed=42)
        s.set_weight("m1", 100)
        s.set_weight("m2", 0)
        candidates = [_model("m1"), _model("m2")]
        # With weight 0 for m2, m1 should always be selected
        for _ in range(10):
            result = s.select(candidates)
            assert result.model_id == "m1"

    def test_negative_weight_raises(self) -> None:
        s = WeightedStrategy()
        with pytest.raises(ValueError, match="non-negative"):
            s.set_weight("m1", -1.0)


class TestFallbackChainStrategy:
    def test_uses_first_successful(self) -> None:
        class EmptyStrategy:
            strategy_name = "empty"

            def select(self, candidates):
                return None

        cheapest = CheapestStrategy()
        chain = FallbackChainStrategy([EmptyStrategy(), cheapest])  # type: ignore[arg-type]
        candidates = [_model("m1")]
        result = chain.select(candidates)
        assert result is not None

    def test_empty_strategies_raises(self) -> None:
        with pytest.raises(ValueError, match="At least one"):
            FallbackChainStrategy([])


class TestHealthBasedStrategy:
    def test_selects_from_healthy(self) -> None:
        s = HealthBasedStrategy()
        s.update_health(
            "healthy_provider",
            ProviderHealth(
                provider_name="healthy_provider",
                status=ProviderStatus.HEALTHY,
            ),
        )
        s.update_health(
            "unhealthy_provider",
            ProviderHealth(
                provider_name="unhealthy_provider",
                status=ProviderStatus.UNHEALTHY,
            ),
        )
        candidates = [
            _model("m1", provider="healthy_provider"),
            _model("m2", provider="unhealthy_provider"),
        ]
        result = s.select(candidates)
        assert result is not None
        assert result.provider_name == "healthy_provider"

    def test_fallback_to_all_when_none_healthy(self) -> None:
        s = HealthBasedStrategy()
        s.update_health(
            "p1",
            ProviderHealth(
                provider_name="p1",
                status=ProviderStatus.UNHEALTHY,
            ),
        )
        candidates = [_model("m1", provider="p1")]
        result = s.select(candidates)
        assert result is not None
