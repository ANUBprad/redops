"""Redis configuration provider extending Kernel ServiceConfiguration."""

from __future__ import annotations

from dataclasses import dataclass

from app.kernel.contracts.config import ServiceConfiguration


@dataclass(frozen=True)
class RedisConfiguration(ServiceConfiguration):
    """Redis connection and event bus configuration.

    Configures Redis Streams-based event bus including stream
    naming, consumer groups, dead-letter policy, and polling.
    """

    db: int = 0
    stream_prefix: str = "redops:events"
    consumer_group: str = "redops-consumers"
    dead_letter_prefix: str = "redops:dead"
    poll_timeout_ms: int = 5000
    batch_size: int = 10
    max_delivery_count: int = 3
    claim_interval_seconds: int = 60
    retry_delay_seconds: float = 1.0
    max_retry_delay_seconds: float = 60.0

    @property
    def connection_url(self) -> str:
        """Return the Redis connection URL."""
        return f"redis://{self.host}:{self.port}/{self.db}"
