"""Tests for capability system."""

from __future__ import annotations

from app.providers.capabilities.capability import Capability
from app.providers.capabilities.capability_set import CapabilitySet


class TestCapability:
    """Tests for Capability enum."""

    def test_capability_values_are_strings(self) -> None:
        assert isinstance(Capability.CHAT.value, str)

    def test_capability_chat_exists(self) -> None:
        assert Capability.CHAT == "chat"

    def test_capability_streaming_exists(self) -> None:
        assert Capability.STREAMING == "streaming"

    def test_capability_vision_exists(self) -> None:
        assert Capability.VISION == "vision"

    def test_capability_embedding_exists(self) -> None:
        assert Capability.EMBEDDING == "embedding"

    def test_capability_tool_calling_exists(self) -> None:
        assert Capability.TOOL_CALLING == "tool_calling"

    def test_all_capabilities_are_unique(self) -> None:
        values = [c.value for c in Capability]
        assert len(values) == len(set(values))


class TestCapabilitySet:
    """Tests for CapabilitySet."""

    def test_empty_set(self) -> None:
        cs = CapabilitySet.empty()
        assert cs.is_empty
        assert cs.count == 0

    def test_of_creates_set(self) -> None:
        cs = CapabilitySet.of(Capability.CHAT, Capability.STREAMING)
        assert cs.count == 2
        assert Capability.CHAT in cs
        assert Capability.STREAMING in cs

    def test_from_iterable(self) -> None:
        caps = [Capability.CHAT, Capability.VISION, Capability.EMBEDDING]
        cs = CapabilitySet.from_iterable(iter(caps))
        assert cs.count == 3

    def test_supports(self) -> None:
        cs = CapabilitySet.of(Capability.CHAT, Capability.STREAMING)
        assert cs.supports(Capability.CHAT)
        assert not cs.supports(Capability.VISION)

    def test_supports_all(self) -> None:
        cs = CapabilitySet.of(Capability.CHAT, Capability.STREAMING, Capability.VISION)
        required = CapabilitySet.of(Capability.CHAT, Capability.STREAMING)
        assert cs.supports_all(required)

    def test_supports_all_false(self) -> None:
        cs = CapabilitySet.of(Capability.CHAT)
        required = CapabilitySet.of(Capability.CHAT, Capability.STREAMING)
        assert not cs.supports_all(required)

    def test_supports_any(self) -> None:
        cs = CapabilitySet.of(Capability.CHAT)
        caps = CapabilitySet.of(Capability.CHAT, Capability.STREAMING)
        assert cs.supports_any(caps)

    def test_supports_any_false(self) -> None:
        cs = CapabilitySet.of(Capability.CHAT)
        caps = CapabilitySet.of(Capability.STREAMING, Capability.VISION)
        assert not cs.supports_any(caps)

    def test_missing(self) -> None:
        cs = CapabilitySet.of(Capability.CHAT)
        required = CapabilitySet.of(Capability.CHAT, Capability.STREAMING)
        missing = cs.missing(required)
        assert missing.count == 1
        assert Capability.STREAMING in missing

    def test_intersection(self) -> None:
        cs1 = CapabilitySet.of(Capability.CHAT, Capability.STREAMING)
        cs2 = CapabilitySet.of(Capability.STREAMING, Capability.VISION)
        result = cs1.intersection(cs2)
        assert result.count == 1
        assert Capability.STREAMING in result

    def test_union(self) -> None:
        cs1 = CapabilitySet.of(Capability.CHAT)
        cs2 = CapabilitySet.of(Capability.STREAMING)
        result = cs1.union(cs2)
        assert result.count == 2

    def test_difference(self) -> None:
        cs1 = CapabilitySet.of(Capability.CHAT, Capability.STREAMING)
        cs2 = CapabilitySet.of(Capability.STREAMING)
        result = cs1.difference(cs2)
        assert result.count == 1
        assert Capability.CHAT in result

    def test_iter_returns_sorted(self) -> None:
        cs = CapabilitySet.of(Capability.STREAMING, Capability.CHAT, Capability.VISION)
        items = list(cs)
        assert items == [Capability.CHAT, Capability.STREAMING, Capability.VISION]

    def test_len(self) -> None:
        cs = CapabilitySet.of(Capability.CHAT, Capability.STREAMING)
        assert len(cs) == 2

    def test_repr(self) -> None:
        cs = CapabilitySet.of(Capability.CHAT)
        assert "chat" in repr(cs)

    def test_deduplication(self) -> None:
        cs = CapabilitySet.of(Capability.CHAT, Capability.CHAT)
        assert cs.count == 1
