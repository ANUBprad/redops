"""Tests for the Groq provider identity, capabilities, and lifecycle."""

import asyncio

from app.providers.capabilities.capability import Capability
from app.providers.capabilities.capability_set import CapabilitySet
from app.providers.groq.provider import GroqProvider


class TestGroqProvider:
    """Tests for GroqProvider."""

    def test_provider_name(self) -> None:
        provider = GroqProvider(api_key="test-key")
        assert provider.provider_name == "groq"

    def test_metadata(self) -> None:
        provider = GroqProvider(api_key="test-key")
        meta = provider.metadata
        assert meta.name == "groq"
        assert meta.display_name == "Groq"
        assert meta.homepage == "https://groq.com"

    def test_capabilities(self) -> None:
        provider = GroqProvider(api_key="test-key")
        caps = provider.capabilities()
        assert caps.supports(Capability.CHAT)
        assert caps.supports(Capability.SYSTEM_PROMPT)
        assert caps.supports(Capability.MULTI_TURN)
        assert caps.supports(Capability.STREAMING)
        assert caps.supports(Capability.TOOL_CALLING)
        assert caps.supports(Capability.FUNCTION_CALLING)
        assert caps.supports(Capability.JSON_MODE)
        assert caps.supports(Capability.REASONING)

    def test_no_embedding_capability(self) -> None:
        """Groq has no embedding API, so it must not advertise embedding."""
        provider = GroqProvider(api_key="test-key")
        caps = provider.capabilities()
        assert not caps.supports(Capability.EMBEDDING)
        assert not caps.supports(Capability.EMBEDDING_DIMENSIONS)

    def test_supports(self) -> None:
        provider = GroqProvider(api_key="test-key")
        assert provider.supports(CapabilitySet.of(Capability.CHAT))
        assert provider.supports(
            CapabilitySet.of(Capability.CHAT, Capability.STREAMING, Capability.TOOL_CALLING)
        )

    def test_lifecycle(self) -> None:
        provider = GroqProvider(api_key="test-key")
        asyncio.run(provider.initialize())
        asyncio.run(provider.start())
        asyncio.run(provider.stop())
        asyncio.run(provider.dispose())
