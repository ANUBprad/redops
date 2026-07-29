"""Model metadata.

Immutable metadata describing a specific model's capabilities,
limits, pricing, and lifecycle status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.providers.capabilities.capability_set import CapabilitySet
from app.providers.models.enums import ModelStatus


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    """Immutable metadata for a specific model.

    Every model in the catalog exposes this metadata, enabling
    the Evaluation Engine to make informed decisions without
    provider-specific knowledge.
    """

    provider_name: str
    model_id: str
    display_name: str = ""
    version: str = ""
    description: str = ""
    context_window: int = 0
    max_output_tokens: int = 0
    capabilities: CapabilitySet = field(default_factory=CapabilitySet.empty)
    status: ModelStatus = ModelStatus.ACTIVE
    release_date: date | None = None
    deprecation_date: date | None = None
    input_price_per_1k: float = 0.0
    output_price_per_1k: float = 0.0
    cached_price_per_1k: float = 0.0
    latency_tier: str = "standard"
    modalities: tuple[str, ...] = ()
    family: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Check if the model is currently active."""
        return self.status == ModelStatus.ACTIVE

    @property
    def is_deprecated(self) -> bool:
        """Check if the model is deprecated."""
        return self.status == ModelStatus.DEPRECATED

    LONG_CONTEXT_THRESHOLD: int = 100_000

    @property
    def supports_long_context(self) -> bool:
        """Check if the model has extended context."""
        return self.context_window > self.LONG_CONTEXT_THRESHOLD

    def supports_capability(self, capability: CapabilitySet) -> bool:
        """Check if the model supports all given capabilities."""
        return self.capabilities.supports_all(capability)

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"ModelMetadata(provider={self.provider_name!r}, "
            f"model={self.model_id!r}, "
            f"context={self.context_window})"
        )
