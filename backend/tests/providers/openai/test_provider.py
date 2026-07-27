"""Tests for OpenAI provider initialization and capabilities."""

import pytest

from app.providers.capabilities.capability import Capability
from app.providers.openai.provider import OpenAIProvider


class TestOpenAIProvider:
    """Tests for OpenAIProvider."""

    def test_provider_name(self) -> None:
        provider = OpenAIProvider(api_key="test-key")
        assert provider.provider_name == "openai"

    def test_metadata(self) -> None:
        provider = OpenAIProvider(api_key="test-key")
        meta = provider.metadata
        assert meta.name == "openai"
        assert meta.display_name == "OpenAI"

    def test_capabilities(self) -> None:
        provider = OpenAIProvider(api_key="test-key")
        caps = provider.capabilities()
        assert caps.supports(Capability.CHAT)
        assert caps.supports(Capability.STREAMING)
        assert caps.supports(Capability.TOOL_CALLING)
        assert caps.supports(Capability.REASONING)
        assert caps.supports(Capability.VISION)
        assert caps.supports(Capability.STRUCTURED_OUTPUT)
        assert caps.supports(Capability.SEED)

    def test_supports(self) -> None:
        provider = OpenAIProvider(api_key="test-key")
        from app.providers.capabilities.capability_set import CapabilitySet
        assert provider.supports(CapabilitySet.of(Capability.CHAT))
        assert provider.supports(CapabilitySet.of(Capability.STREAMING, Capability.TOOL_CALLING))

    def test_lifecycle(self) -> None:
        provider = OpenAIProvider(api_key="test-key")
        import asyncio
        asyncio.run(provider.initialize())
        asyncio.run(provider.start())
        asyncio.run(provider.stop())
        asyncio.run(provider.dispose())
