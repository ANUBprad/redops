"""Temporal worker bootstrap.

This module provides the worker startup logic.
Workflows and activities are registered here as they are implemented.
"""

from temporalio.client import Client as TemporalClient
from temporalio.worker import Worker

from app.core.config import AppConfig


async def start_worker(
    temporal_client: TemporalClient,
    config: AppConfig,
) -> Worker:
    """Create and start a Temporal worker for the application task queue.

    Args:
        temporal_client: The connected Temporal client.
        config: The application configuration.

    Returns:
        The started Worker instance.

    """
    worker = Worker(
        client=temporal_client,
        task_queue=config.temporal_task_queue,
        activities=[],  # Register activities here
        workflows=[],  # Register workflows here
    )

    await worker.run()

    return worker
