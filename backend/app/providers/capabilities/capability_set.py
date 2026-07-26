"""Capability set for grouping and querying capabilities.

Provides an immutable, queryable collection of capabilities that
a provider or model supports. Supports set operations for
capability comparison and matching.
"""

from __future__ import annotations

from collections.abc import Iterator  # noqa: TC003
from dataclasses import dataclass, field

from app.providers.capabilities.capability import Capability  # noqa: TC001


@dataclass(frozen=True, slots=True)
class CapabilitySet:
    """Immutable set of capabilities.

    Provides efficient membership testing and set operations
    for capability matching and comparison.
    """

    _capabilities: frozenset[Capability] = field(default_factory=frozenset)

    @classmethod
    def empty(cls) -> CapabilitySet:
        """Create an empty capability set."""
        return cls(_capabilities=frozenset())

    @classmethod
    def of(cls, *capabilities: Capability) -> CapabilitySet:
        """Create a capability set from individual capabilities."""
        return cls(_capabilities=frozenset(capabilities))

    @classmethod
    def from_iterable(cls, capabilities: Iterator[Capability]) -> CapabilitySet:
        """Create a capability set from an iterable."""
        return cls(_capabilities=frozenset(capabilities))

    def supports(self, capability: Capability) -> bool:
        """Check if this set includes the given capability."""
        return capability in self._capabilities

    def supports_all(self, capabilities: CapabilitySet) -> bool:
        """Check if this set includes all given capabilities."""
        return self._capabilities.issuperset(capabilities._capabilities)

    def supports_any(self, capabilities: CapabilitySet) -> bool:
        """Check if this set includes any of the given capabilities."""
        return bool(self._capabilities.intersection(capabilities._capabilities))

    def missing(self, required: CapabilitySet) -> CapabilitySet:
        """Return capabilities from required that are not in this set."""
        missing_caps = required._capabilities - self._capabilities
        return CapabilitySet(_capabilities=missing_caps)

    def intersection(self, other: CapabilitySet) -> CapabilitySet:
        """Return capabilities common to both sets."""
        return CapabilitySet(_capabilities=self._capabilities & other._capabilities)

    def union(self, other: CapabilitySet) -> CapabilitySet:
        """Return all capabilities from both sets."""
        return CapabilitySet(_capabilities=self._capabilities | other._capabilities)

    def difference(self, other: CapabilitySet) -> CapabilitySet:
        """Return capabilities in this set but not in other."""
        return CapabilitySet(_capabilities=self._capabilities - other._capabilities)

    @property
    def is_empty(self) -> bool:
        """Check if the set contains no capabilities."""
        return len(self._capabilities) == 0

    @property
    def count(self) -> int:
        """Return the number of capabilities."""
        return len(self._capabilities)

    def __iter__(self) -> Iterator[Capability]:
        """Iterate over capabilities."""
        return iter(sorted(self._capabilities, key=lambda c: c.value))

    def __len__(self) -> int:
        """Return the number of capabilities."""
        return len(self._capabilities)

    def __contains__(self, capability: Capability) -> bool:
        """Check membership."""
        return capability in self._capabilities

    def __repr__(self) -> str:
        """Return string representation."""
        items = ", ".join(c.value for c in sorted(self._capabilities, key=lambda c: c.value))
        return f"CapabilitySet({{{items}}})"
