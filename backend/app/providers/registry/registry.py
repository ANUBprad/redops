"""Provider registry.

Central registry for provider instances. The Evaluation Engine
interacts exclusively through this registry to discover,
resolve, and monitor providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.providers.capabilities.capability import Capability  # noqa: TC001
from app.providers.capabilities.capability_set import CapabilitySet  # noqa: TC001
from app.providers.contracts.base import BaseProvider  # noqa: TC001
from app.providers.health.provider_health import ProviderHealth
from app.providers.health.status import ProviderStatus


@dataclass
class ProviderRegistry:
    """Central registry for AI providers.

    Manages provider registration, resolution, discovery,
    and health reporting. The Evaluation Engine uses this
    as the sole entry point for provider interaction.
    """

    _providers: dict[str, BaseProvider] = field(default_factory=dict, init=False)

    def register(self, provider: BaseProvider) -> None:
        """Register a provider.

        Args:
            provider: The provider instance to register.

        Raises:
            ValueError: If a provider with the same name exists.

        """
        name = provider.provider_name
        if name in self._providers:
            msg = f"Provider '{name}' is already registered"
            raise ValueError(msg)
        self._providers[name] = provider

    def unregister(self, provider_name: str) -> None:
        """Remove a provider from the registry.

        Args:
            provider_name: The name of the provider to remove.

        """
        self._providers.pop(provider_name, None)

    def resolve(self, provider_name: str) -> BaseProvider:
        """Resolve a provider by name.

        Args:
            provider_name: The name of the provider.

        Returns:
            The provider instance.

        Raises:
            KeyError: If the provider is not registered.

        """
        provider = self._providers.get(provider_name)
        if provider is None:
            msg = f"Provider '{provider_name}' is not registered"
            raise KeyError(msg)
        return provider

    def discover(self, capability: Capability) -> list[BaseProvider]:
        """Discover providers supporting a capability.

        Args:
            capability: The capability to search for.

        Returns:
            List of providers supporting the capability.

        """
        return [
            p for p in self._providers.values()
            if p.capabilities().supports(capability)
        ]

    def discover_all(self, capabilities: CapabilitySet) -> list[BaseProvider]:
        """Discover providers supporting all capabilities.

        Args:
            capabilities: The required capabilities.

        Returns:
            List of providers supporting all capabilities.

        """
        return [
            p for p in self._providers.values()
            if p.capabilities().supports_all(capabilities)
        ]

    async def health(self) -> dict[str, ProviderHealth]:
        """Check health of all registered providers.

        Returns:
            Mapping of provider name to health status.

        """
        results: dict[str, ProviderHealth] = {}
        for name, provider in self._providers.items():
            try:
                is_healthy = await provider.health()
                if is_healthy:
                    try:
                        results[name] = await provider.detailed_health()
                    except (AttributeError, NotImplementedError):
                        results[name] = ProviderHealth(
                            provider_name=name,
                            status=ProviderStatus.HEALTHY,
                        )
                else:
                    results[name] = ProviderHealth(
                        provider_name=name,
                        status=ProviderStatus.UNHEALTHY,
                        message="Health check returned False",
                    )
            except Exception:  # noqa: BLE001
                results[name] = ProviderHealth(
                    provider_name=name,
                    status=ProviderStatus.UNHEALTHY,
                    message="Health check failed",
                )
        return results

    def list_providers(self) -> list[BaseProvider]:
        """Return all registered providers."""
        return list(self._providers.values())

    def list_provider_names(self) -> list[str]:
        """Return names of all registered providers."""
        return list(self._providers.keys())

    def is_registered(self, provider_name: str) -> bool:
        """Check if a provider is registered."""
        return provider_name in self._providers

    def count(self) -> int:
        """Return the number of registered providers."""
        return len(self._providers)
