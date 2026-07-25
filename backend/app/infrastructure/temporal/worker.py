"""Temporal worker factory with activity and workflow registration frameworks.

Provides typed registries for activities and workflows, and a factory
that constructs Temporal Workers from those registrations.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from temporalio.worker import Worker

if TYPE_CHECKING:
    from temporalio.client import Client as TemporalClient

    from app.infrastructure.config.temporal import TemporalConfiguration

ActivityType = Callable[..., Any]
WorkflowType = type[Any]


class ActivityRegistry:
    """Registry for Temporal activities.

    Activities are registered by name for discovery and worker
    construction. Provides iteration and count operations.
    """

    def __init__(self) -> None:
        """Initialize an empty activity registry."""
        self._activities: dict[str, ActivityType] = {}

    def register(self, activity: ActivityType, name: str | None = None) -> None:
        """Register an activity function.

        Args:
            activity: The activity function to register.
            name: Optional display name (defaults to function name).

        """
        activity_name = name or activity.__name__
        self._activities[activity_name] = activity

    def unregister(self, name: str) -> None:
        """Remove a registered activity by name.

        Args:
            name: The name of the activity to remove.

        """
        self._activities.pop(name, None)

    def get_all(self) -> list[ActivityType]:
        """Return all registered activity functions."""
        return list(self._activities.values())

    @property
    def count(self) -> int:
        """Return the number of registered activities."""
        return len(self._activities)


class WorkflowRegistry:
    """Registry for Temporal workflows.

    Workflows are registered as classes for worker construction.
    """

    def __init__(self) -> None:
        """Initialize an empty workflow registry."""
        self._workflows: dict[str, WorkflowType] = {}

    def register(self, workflow: WorkflowType, name: str | None = None) -> None:
        """Register a workflow class.

        Args:
            workflow: The workflow class to register.
            name: Optional display name (defaults to class name).

        """
        workflow_name = name or workflow.__name__
        self._workflows[workflow_name] = workflow

    def unregister(self, name: str) -> None:
        """Remove a registered workflow by name.

        Args:
            name: The name of the workflow to remove.

        """
        self._workflows.pop(name, None)

    def get_all(self) -> list[WorkflowType]:
        """Return all registered workflow classes."""
        return list(self._workflows.values())

    @property
    def count(self) -> int:
        """Return the number of registered workflows."""
        return len(self._workflows)


class TemporalWorkerFactory:
    """Factory for creating Temporal Workers from registrations.

    Uses the ActivityRegistry and WorkflowRegistry to construct
    workers with all registered activities and workflows.
    """

    def __init__(
        self,
        config: TemporalConfiguration,
        activity_registry: ActivityRegistry,
        workflow_registry: WorkflowRegistry,
    ) -> None:
        """Initialize with config and registries."""
        self._config = config
        self._activity_registry = activity_registry
        self._workflow_registry = workflow_registry

    async def create_worker(self, temporal_client: TemporalClient) -> Worker:
        """Create a configured Temporal Worker.

        Args:
            temporal_client: The connected Temporal client.

        Returns:
            A configured (unstarted) Worker instance.

        """
        return Worker(
            client=temporal_client,
            task_queue=self._config.task_queue,
            activities=self._activity_registry.get_all(),
            workflows=self._workflow_registry.get_all(),
            max_concurrent_activities=self._config.worker_max_concurrent_activities,
            max_concurrent_workflow_tasks=self._config.worker_max_concurrent_workflows,
            identity=self._config.identity,
        )
