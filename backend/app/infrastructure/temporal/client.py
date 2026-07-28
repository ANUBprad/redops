"""Temporal client factory with lifecycle management.

Provides a managed Temporal client connection that implements the
LifecycleService interface for integration with the application
lifecycle manager.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from temporalio.client import Client as TemporalClient

from app.kernel.lifecycle.lifecycle import LifecycleService

if TYPE_CHECKING:
    from app.infrastructure.config.temporal import TemporalConfiguration


class TemporalClientFactory(LifecycleService):
    """Managed Temporal client connection.

    Encapsulates the Temporal client connection lifecycle, providing
    initialize/start/stop/dispose semantics aligned with the Kernel's
    LifecycleService contract.
    """

    def __init__(self, config: TemporalConfiguration) -> None:
        """Initialize with Temporal configuration."""
        self._config = config
        self._client: TemporalClient | None = None

    @property
    def client(self) -> TemporalClient:
        """Return the connected Temporal client.

        Raises:
            RuntimeError: If the client has not been started.

        """
        if self._client is None:
            raise RuntimeError("Temporal client not initialized")
        return self._client

    @property
    def is_connected(self) -> bool:
        """Return whether the Temporal client is connected."""
        return self._client is not None

    async def initialize(self) -> None:
        """No-op initialization; connection happens in start()."""
        self._client = None

    async def start(self) -> None:
        """Connect to the Temporal server."""
        if self._client is not None:
            return
        self._client = await TemporalClient.connect(
            target_host=self._config.target_host,
            namespace=self._config.namespace,
            identity=self._config.identity,
        )

    async def stop(self) -> None:
        """Disconnect from the Temporal server."""
        await self.dispose()

    async def dispose(self) -> None:
        """Release the Temporal client connection."""
        if self._client is not None:
            self._client = None

    async def health(self) -> bool:
        """Check if the Temporal server is reachable.

        Returns:
            True if Temporal is reachable, False otherwise.

        """
        if self._client is None:
            return False
        try:
            return await self._client.service_client.check_health()
        except Exception:
            return False
