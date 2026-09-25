"""Tests for Groq provider registration and pricing."""

from app.providers.capabilities.capability import Capability
from app.providers.cost.defaults import build_default_cost_calculator
from app.providers.groq.provider import GroqProvider
from app.providers.registry.registry import ProviderRegistry


class TestGroqRegistration:
    """Tests for registering GroqProvider in the ProviderRegistry."""

    def test_registry_register_and_resolve(self) -> None:
        registry = ProviderRegistry()
        registry.register(GroqProvider(api_key="test-key"))
        assert registry.is_registered("groq")
        resolved = registry.resolve("groq")
        assert resolved.provider_name == "groq"

    def test_registry_discover_chat(self) -> None:
        registry = ProviderRegistry()
        registry.register(GroqProvider(api_key="test-key"))
        providers = registry.discover(Capability.CHAT)
        assert any(p.provider_name == "groq" for p in providers)

    def test_registry_not_discovered_for_embedding(self) -> None:
        """Groq has no embedding API and must not be returned for embeddings."""
        registry = ProviderRegistry()
        registry.register(GroqProvider(api_key="test-key"))
        providers = registry.discover(Capability.EMBEDDING)
        assert all(p.provider_name != "groq" for p in providers)

    def test_duplicate_registration_raises(self) -> None:
        registry = ProviderRegistry()
        registry.register(GroqProvider(api_key="test-key"))
        try:
            registry.register(GroqProvider(api_key="test-key"))
        except ValueError:
            assert True
        else:
            raise AssertionError("duplicate Groq registration should raise ValueError")


class TestGroqPricing:
    """Tests for Groq pricing in the default cost calculator."""

    def test_groq_pricing_registered(self) -> None:
        calculator = build_default_cost_calculator()
        models = {m.model_id for m in calculator.list_pricing_models() if m.provider_name == "groq"}
        assert "llama-3.3-70b-versatile" in models
        assert "llama-3.1-8b-instant" in models
        assert "mixtral-8x7b-32768" in models
