"""Temporal worker lifecycle integration.

Provides a LifecycleService that manages the Temporal Worker's
startup, shutdown, and health reporting aligned with the Kernel's
LifecycleService contract.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

from app.kernel.lifecycle.lifecycle import LifecycleService

if TYPE_CHECKING:
    from app.infrastructure.config.temporal import TemporalConfiguration
    from app.infrastructure.temporal.client import TemporalClientFactory
    from app.infrastructure.temporal.worker import TemporalWorkerFactory


class TemporalWorkerLifecycle(LifecycleService):
    """Managed Temporal Worker lifecycle.

    Creates a Temporal Worker and manages its run loop as a background
    asyncio task. Integrates with the application lifecycle manager
    for coordinated startup and shutdown.

    The worker is started in the background so it does not block
    the application startup sequence.
    """

    def __init__(
        self,
        worker_factory: TemporalWorkerFactory,
        client_factory: TemporalClientFactory,
        config: TemporalConfiguration,
    ) -> None:
        """Initialize with worker factory, client factory, and config."""
        self._worker_factory = worker_factory
        self._client_factory = client_factory
        self._config = config
        self._worker: Any = None
        self._worker_task: asyncio.Task[Any] | None = None

    # These types are used in type hints but with `from __future__ import annotations`
    # they are strings at runtime, so imports are under TYPE_CHECKING above.
    # TemporalClientFactory, TemporalWorkerFactory, TemporalConfiguration

    # pyright: ignore[reportUnusedImport]

    async def initialize(self) -> None:
        """Create the worker instance without starting it."""
        if not self._config.enable_worker:
            return
        client = self._client_factory.client
        self._worker = await self._worker_factory.create_worker(client)

    async def start(self) -> None:
        """Start the Temporal Worker in a background task."""
        if self._worker is None or not self._config.enable_worker:
            return
        self._worker_task = asyncio.create_task(
            self._worker.run(),
            name="temporal-worker",
        )

    async def stop(self) -> None:
        """Signal the worker to shut down gracefully."""
        self._worker_task = None

    async def dispose(self) -> None:
        """Cancel the worker task and clean up."""
        if self._worker_task is not None and not self._worker_task.done():
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None
        self._worker = None

    async def health(self) -> bool:
        """Check if the Temporal Worker is running.

        Returns:
            True if the worker is active, False otherwise.

        """
        if not self._config.enable_worker:
            return True
        if self._worker_task is None:
            return False
        return not self._worker_task.done()
