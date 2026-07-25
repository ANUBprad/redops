"""Temporal configuration provider extending Kernel ServiceConfiguration."""

from __future__ import annotations

from dataclasses import dataclass

from app.kernel.contracts.config import ServiceConfiguration


@dataclass(frozen=True)
class TemporalConfiguration(ServiceConfiguration):
    """Temporal Server and Worker configuration.

    Configures Temporal Server connection, namespace, task queue,
    and worker concurrency settings.
    """

    namespace: str = "default"
    task_queue: str = "redops-eval"
    worker_max_concurrent_activities: int = 100
    worker_max_concurrent_workflows: int = 50
    worker_max_concurrent_local_activities: int = 50
    enable_worker: bool = True
    identity: str = "redops-eval-worker"
    client_timeout_seconds: float = 30.0

    @property
    def target_host(self) -> str:
        """Return the formatted target host string."""
        return f"{self.host}:{self.port}"
