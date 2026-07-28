"""Base provider contract.

Defines the foundational interface that every provider must
implement. Handles provider identity, lifecycle, health,
and capability declaration.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from app.kernel.lifecycle.lifecycle import LifecycleService

if TYPE_CHECKING:
    from app.providers.capabilities.capability_set import CapabilitySet
    from app.providers.health.provider_health import ProviderHealth
    from app.providers.metadata.provider import ProviderMetadata


class BaseProvider(LifecycleService):
    """Abstract base for all AI providers.

    Every provider must implement this interface, which provides
    identity, capability declaration, and lifecycle management.
    The Evaluation Engine interacts only through these contracts.

    Lifecycle:
        1. initialize() - Set up connection pools, validate config.
        2. start() - Begin accepting requests.
        3. stop() - Stop accepting new requests.
        4. dispose() - Release all resources.

    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique provider identifier.

        This must be a stable, unique string (e.g., 'openai',
        'anthropic', 'ollama'). Used for registry lookups.

        """

    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        """Return static provider metadata."""

    @abstractmethod
    def capabilities(self) -> CapabilitySet:
        """Return the set of capabilities this provider supports.

        Returns:
            A CapabilitySet describing all supported features.

        """

    @abstractmethod
    async def health(self) -> bool:
        """Check provider health status.

        Returns:
            True if the provider is healthy and available.

        """

    @abstractmethod
    async def detailed_health(self) -> ProviderHealth:
        """Return detailed provider health information.

        Returns:
            A ProviderHealth describing current availability
            with capability and latency details.

        """

    @abstractmethod
    def supports(self, capability: CapabilitySet) -> bool:
        """Check if this provider supports all given capabilities.

        Args:
            capability: The capabilities to check.

        Returns:
            True if all capabilities are supported.

        """
