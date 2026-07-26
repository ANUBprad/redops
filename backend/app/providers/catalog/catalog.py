"""Model catalog.

An immutable, queryable collection of model metadata.
Supports filtering by provider, capabilities, and status.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.providers.capabilities.capability import Capability  # noqa: TC001
from app.providers.capabilities.capability_set import CapabilitySet  # noqa: TC001
from app.providers.catalog.model import ModelMetadata  # noqa: TC001
from app.providers.models.enums import ModelStatus


@dataclass
class ModelCatalog:
    """Queryable catalog of model metadata.

    Models are registered once and the catalog is treated as
    immutable after initialization. Queries filter the
    registered models by various criteria.
    """

    _models: dict[str, ModelMetadata] = field(default_factory=dict, init=False)

    def register(self, model: ModelMetadata) -> None:
        """Register a model in the catalog.

        Args:
            model: The model metadata to register.

        """
        key = f"{model.provider_name}:{model.model_id}"
        self._models[key] = model

    def unregister(self, provider_name: str, model_id: str) -> None:
        """Remove a model from the catalog.

        Args:
            provider_name: The provider name.
            model_id: The model identifier.

        """
        key = f"{provider_name}:{model_id}"
        self._models.pop(key, None)

    def get(self, provider_name: str, model_id: str) -> ModelMetadata | None:
        """Retrieve a specific model.

        Args:
            provider_name: The provider name.
            model_id: The model identifier.

        Returns:
            The model metadata, or None if not found.

        """
        key = f"{provider_name}:{model_id}"
        return self._models.get(key)

    def list_all(self) -> list[ModelMetadata]:
        """Return all registered models."""
        return list(self._models.values())

    def list_by_provider(self, provider_name: str) -> list[ModelMetadata]:
        """Return models from a specific provider."""
        return [m for m in self._models.values() if m.provider_name == provider_name]

    def list_active(self) -> list[ModelMetadata]:
        """Return only active models."""
        return [m for m in self._models.values() if m.status == ModelStatus.ACTIVE]

    def list_with_capability(self, capability: Capability) -> list[ModelMetadata]:
        """Return models supporting a specific capability."""
        return [
            m for m in self._models.values()
            if m.capabilities.supports(capability)
        ]

    def list_with_capabilities(self, capabilities: CapabilitySet) -> list[ModelMetadata]:
        """Return models supporting all given capabilities."""
        return [
            m for m in self._models.values()
            if m.capabilities.supports_all(capabilities)
        ]

    def search_by_context_window(self, min_tokens: int) -> list[ModelMetadata]:
        """Return models with at least min_tokens context window."""
        return [
            m for m in self._models.values()
            if m.context_window >= min_tokens
        ]

    def search_by_price(
        self,
        *,
        max_input_price: float | None = None,
        max_output_price: float | None = None,
    ) -> list[ModelMetadata]:
        """Return models within a price range."""
        results = list(self._models.values())
        if max_input_price is not None:
            results = [m for m in results if m.input_price_per_1k <= max_input_price]
        if max_output_price is not None:
            results = [m for m in results if m.output_price_per_1k <= max_output_price]
        return results

    def count(self) -> int:
        """Return the number of registered models."""
        return len(self._models)
