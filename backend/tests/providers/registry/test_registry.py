"""Tests for provider registry."""

from __future__ import annotations

from typing import Any

import pytest

from app.providers.capabilities.capability import Capability
from app.providers.capabilities.capability_set import CapabilitySet
from app.providers.contracts.base import BaseProvider
from app.providers.health.provider_health import ProviderHealth
from app.providers.health.status import ProviderStatus
from app.providers.metadata.provider import ProviderMetadata
from app.providers.registry.registry import ProviderRegistry


class MockProvider(BaseProvider):
    """Mock provider for testing."""

    def __init__(
        self,
        name: str = "mock",
        caps: CapabilitySet | None = None,
    ) -> None:
        self._name = name
        self._caps = caps or CapabilitySet.of(Capability.CHAT)
        self._initialized = False
        self._started = False

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(name=self._name, display_name=f"Mock {self._name}")

    def capabilities(self) -> CapabilitySet:
        return self._caps

    async def health(self) -> bool:
        return True

    async def detailed_health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_name=self._name,
            status=ProviderStatus.HEALTHY,
        )

    def supports(self, capability: CapabilitySet) -> bool:
        return self._caps.supports_all(capability)

    async def initialize(self) -> None:
        self._initialized = True

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    async def dispose(self) -> None:
        self._initialized = False


class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    def test_register_and_resolve(self) -> None:
        reg = ProviderRegistry()
        provider = MockProvider("openai")
        reg.register(provider)
        assert reg.resolve("openai") is provider

    def test_register_duplicate_raises(self) -> None:
        reg = ProviderRegistry()
        reg.register(MockProvider("openai"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(MockProvider("openai"))

    def test_resolve_nonexistent_raises(self) -> None:
        reg = ProviderRegistry()
        with pytest.raises(KeyError, match="not registered"):
            reg.resolve("nonexistent")

    def test_unregister(self) -> None:
        reg = ProviderRegistry()
        reg.register(MockProvider("openai"))
        reg.unregister("openai")
        assert not reg.is_registered("openai")

    def test_discover(self) -> None:
        reg = ProviderRegistry()
        reg.register(MockProvider("openai", CapabilitySet.of(Capability.CHAT)))
        reg.register(MockProvider("vision", CapabilitySet.of(Capability.VISION)))
        result = reg.discover(Capability.VISION)
        assert len(result) == 1
        assert result[0].provider_name == "vision"

    def test_discover_all(self) -> None:
        reg = ProviderRegistry()
        reg.register(MockProvider(
            "multi",
            CapabilitySet.of(Capability.CHAT, Capability.STREAMING),
        ))
        reg.register(MockProvider("chat_only", CapabilitySet.of(Capability.CHAT)))
        result = reg.discover_all(CapabilitySet.of(Capability.CHAT, Capability.STREAMING))
        assert len(result) == 1

    def test_list_providers(self) -> None:
        reg = ProviderRegistry()
        reg.register(MockProvider("a"))
        reg.register(MockProvider("b"))
        assert reg.count() == 2

    def test_list_provider_names(self) -> None:
        reg = ProviderRegistry()
        reg.register(MockProvider("a"))
        reg.register(MockProvider("b"))
        names = reg.list_provider_names()
        assert "a" in names
        assert "b" in names

    def test_is_registered(self) -> None:
        reg = ProviderRegistry()
        reg.register(MockProvider("openai"))
        assert reg.is_registered("openai")
        assert not reg.is_registered("anthropic")

    @pytest.mark.asyncio
    async def test_health(self) -> None:
        reg = ProviderRegistry()
        reg.register(MockProvider("openai"))
        health = await reg.health()
        assert "openai" in health
        assert health["openai"].is_healthy
