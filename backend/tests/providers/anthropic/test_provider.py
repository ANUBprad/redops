"""Tests for Anthropic provider initialization and capabilities."""

import asyncio

from app.providers.anthropic.provider import AnthropicProvider
from app.providers.capabilities.capability import Capability
from app.providers.capabilities.capability_set import CapabilitySet


class TestAnthropicProvider:
    """Tests for AnthropicProvider."""

    def test_provider_name(self) -> None:
        provider = AnthropicProvider(api_key="test-key")
        assert provider.provider_name == "anthropic"

    def test_metadata(self) -> None:
        provider = AnthropicProvider(api_key="test-key")
        meta = provider.metadata
        assert meta.name == "anthropic"
        assert meta.display_name == "Anthropic"
        assert meta.version == "0.1.0"
        assert "anthropic" in meta.tags
        assert "claude" in meta.tags

    def test_capabilities(self) -> None:
        provider = AnthropicProvider(api_key="test-key")
        caps = provider.capabilities()
        assert caps.supports(Capability.CHAT)
        assert caps.supports(Capability.STREAMING)
        assert caps.supports(Capability.TOOL_CALLING)
        assert caps.supports(Capability.REASONING)
        assert caps.supports(Capability.VISION)
        assert caps.supports(Capability.SYSTEM_PROMPT)
        assert caps.supports(Capability.MULTI_TURN)
        assert caps.supports(Capability.IMAGE_URL)
        assert caps.supports(Capability.IMAGE_BASE64)
        assert caps.supports(Capability.MULTI_IMAGE)
        assert caps.supports(Capability.FUNCTION_CALLING)
        assert caps.supports(Capability.PARALLEL_TOOL_CALLS)
        assert caps.supports(Capability.STOP_SEQUENCES)
        assert caps.supports(Capability.TEMPERATURE)
        assert caps.supports(Capability.TOP_P)
        assert caps.supports(Capability.LONG_CONTEXT)
        assert caps.supports(Capability.VISION_CONTEXT)
        assert caps.supports(Capability.EXTENDED_THINKING)
        assert caps.supports(Capability.PROMPT_CACHING)

    def test_supports(self) -> None:
        provider = AnthropicProvider(api_key="test-key")
        assert provider.supports(CapabilitySet.of(Capability.CHAT))
        assert provider.supports(CapabilitySet.of(Capability.STREAMING, Capability.TOOL_CALLING))

    def test_does_not_support_missing(self) -> None:
        provider = AnthropicProvider(api_key="test-key")
        # Anthropic doesn't have STRUCTURED_OUTPUT or SEED
        assert not provider.supports(CapabilitySet.of(Capability.STRUCTURED_OUTPUT))
        assert not provider.supports(CapabilitySet.of(Capability.SEED))

    def test_initialize(self) -> None:
        provider = AnthropicProvider(api_key="test-key")
        asyncio.run(provider.initialize())

    def test_start_stop(self) -> None:
        provider = AnthropicProvider(api_key="test-key")
        asyncio.run(provider.start())
        asyncio.run(provider.stop())

    def test_dispose(self) -> None:
        provider = AnthropicProvider(api_key="test-key")
        asyncio.run(provider.dispose())
