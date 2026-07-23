"""Temporal client initialization and lifecycle management."""

from temporalio.client import Client as TemporalClient

from app.core.config import AppConfig


async def create_temporal_client(config: AppConfig) -> TemporalClient:
    """Create and return a Temporal client connection.

    Args:
        config: The application configuration with Temporal connection settings.

    Returns:
        A connected Temporal client.

    """
    client = await TemporalClient.connect(
        target_host=f"{config.temporal_host}:{config.temporal_port}",
        namespace=config.temporal_namespace,
    )
    return client
