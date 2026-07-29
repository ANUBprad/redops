"""Provider metadata.

Immutable metadata describing a provider's identity and
static characteristics. Used for registry display, catalog
queries, and provider discovery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    """Static metadata about a provider.

    Describes the provider's identity, capabilities, and
    contact information. Immutable once created.
    """

    name: str
    display_name: str
    description: str = ""
    version: str = "0.1.0"
    author: str = ""
    homepage: str = ""
    documentation_url: str = ""
    supported_regions: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        """Return string representation."""
        return f"ProviderMetadata(name={self.name!r}, version={self.version!r})"
