"""Tests for model catalog."""

from __future__ import annotations

from app.providers.capabilities.capability import Capability
from app.providers.capabilities.capability_set import CapabilitySet
from app.providers.catalog.catalog import ModelCatalog
from app.providers.catalog.model import ModelMetadata
from app.providers.models.enums import ModelStatus


def _make_model(
    provider: str = "test",
    model_id: str = "model-1",
    context_window: int = 4096,
    input_price: float = 0.01,
    output_price: float = 0.02,
    capabilities: CapabilitySet | None = None,
    status: ModelStatus = ModelStatus.ACTIVE,
) -> ModelMetadata:
    return ModelMetadata(
        provider_name=provider,
        model_id=model_id,
        display_name=f"Test {model_id}",
        context_window=context_window,
        max_output_tokens=2048,
        capabilities=capabilities or CapabilitySet.of(Capability.CHAT),
        status=status,
        input_price_per_1k=input_price,
        output_price_per_1k=output_price,
    )


class TestModelMetadata:
    """Tests for ModelMetadata."""

    def test_is_active(self) -> None:
        m = _make_model(status=ModelStatus.ACTIVE)
        assert m.is_active

    def test_is_not_active_when_deprecated(self) -> None:
        m = _make_model(status=ModelStatus.DEPRECATED)
        assert not m.is_active
        assert m.is_deprecated

    def test_supports_long_context(self) -> None:
        m = _make_model(context_window=200_000)
        assert m.supports_long_context

    def test_does_not_support_long_context(self) -> None:
        m = _make_model(context_window=8192)
        assert not m.supports_long_context

    def test_supports_capability(self) -> None:
        caps = CapabilitySet.of(Capability.CHAT, Capability.STREAMING)
        m = _make_model(capabilities=caps)
        assert m.supports_capability(CapabilitySet.of(Capability.CHAT))
        assert not m.supports_capability(CapabilitySet.of(Capability.VISION))


class TestModelCatalog:
    """Tests for ModelCatalog."""

    def test_register_and_get(self) -> None:
        catalog = ModelCatalog()
        m = _make_model()
        catalog.register(m)
        result = catalog.get("test", "model-1")
        assert result is not None
        assert result.model_id == "model-1"

    def test_get_nonexistent(self) -> None:
        catalog = ModelCatalog()
        assert catalog.get("test", "nonexistent") is None

    def test_unregister(self) -> None:
        catalog = ModelCatalog()
        catalog.register(_make_model())
        catalog.unregister("test", "model-1")
        assert catalog.get("test", "model-1") is None

    def test_list_all(self) -> None:
        catalog = ModelCatalog()
        catalog.register(_make_model(model_id="m1"))
        catalog.register(_make_model(model_id="m2"))
        assert catalog.count() == 2

    def test_list_by_provider(self) -> None:
        catalog = ModelCatalog()
        catalog.register(_make_model(provider="openai", model_id="m1"))
        catalog.register(_make_model(provider="anthropic", model_id="m2"))
        openai_models = catalog.list_by_provider("openai")
        assert len(openai_models) == 1

    def test_list_active(self) -> None:
        catalog = ModelCatalog()
        catalog.register(_make_model(model_id="m1", status=ModelStatus.ACTIVE))
        catalog.register(_make_model(model_id="m2", status=ModelStatus.DEPRECATED))
        active = catalog.list_active()
        assert len(active) == 1

    def test_list_with_capability(self) -> None:
        catalog = ModelCatalog()
        catalog.register(
            _make_model(
                model_id="m1",
                capabilities=CapabilitySet.of(Capability.CHAT, Capability.STREAMING),
            )
        )
        catalog.register(
            _make_model(
                model_id="m2",
                capabilities=CapabilitySet.of(Capability.CHAT),
            )
        )
        streaming = catalog.list_with_capability(Capability.STREAMING)
        assert len(streaming) == 1

    def test_list_with_capabilities(self) -> None:
        catalog = ModelCatalog()
        catalog.register(
            _make_model(
                model_id="m1",
                capabilities=CapabilitySet.of(
                    Capability.CHAT, Capability.STREAMING, Capability.VISION
                ),
            )
        )
        catalog.register(
            _make_model(
                model_id="m2",
                capabilities=CapabilitySet.of(Capability.CHAT),
            )
        )
        result = catalog.list_with_capabilities(
            CapabilitySet.of(Capability.CHAT, Capability.STREAMING),
        )
        assert len(result) == 1

    def test_search_by_context_window(self) -> None:
        catalog = ModelCatalog()
        catalog.register(_make_model(model_id="m1", context_window=4096))
        catalog.register(_make_model(model_id="m2", context_window=200_000))
        result = catalog.search_by_context_window(100_000)
        assert len(result) == 1

    def test_search_by_price(self) -> None:
        catalog = ModelCatalog()
        catalog.register(_make_model(model_id="m1", input_price=0.001))
        catalog.register(_make_model(model_id="m2", input_price=0.05))
        result = catalog.search_by_price(max_input_price=0.01)
        assert len(result) == 1

    def test_count(self) -> None:
        catalog = ModelCatalog()
        assert catalog.count() == 0
        catalog.register(_make_model())
        assert catalog.count() == 1
