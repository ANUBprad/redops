"""DI container setup for infrastructure components.

Wires all infrastructure dependencies into the Kernel DIContainer
with appropriate lifetimes.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from redis.asyncio import Redis as AsyncRedis

from app.agents.temporal.activities import (
    cancel_agent_run_activity,
    complete_agent_run_activity,
    create_agent_run_activity,
    fail_agent_run_activity,
    queue_agent_run_activity,
    start_agent_run_activity,
    update_agent_run_progress_activity,
)
from app.agents.temporal.workflow import AgentRunWorkflow
from app.evaluation.temporal.activities import (
    cancel_run_activity,
    complete_run_activity,
    create_run_activity,
    fail_run_activity,
    queue_run_activity,
    start_run_activity,
    update_progress_activity,
)
from app.evaluation.temporal.workflow import EvaluationRunWorkflow
from app.infrastructure.config.database import DatabaseConfiguration
from app.infrastructure.config.logging import LoggingConfiguration
from app.infrastructure.config.redis import RedisConfiguration
from app.infrastructure.config.temporal import TemporalConfiguration
from app.infrastructure.database.engine import DatabaseEngine
from app.infrastructure.database.session import SessionManager
from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.event_bus.dead_letter import DeadLetterQueue
from app.infrastructure.event_bus.redis_event_bus import RedisStreamsEventBus
from app.infrastructure.event_bus.serialization import JsonEventSerializer
from app.infrastructure.plugin.discovery import (
    EntryPointPluginDiscovery,
    FilesystemPluginDiscovery,
)
from app.infrastructure.plugin.loader import PluginLoaderImpl
from app.infrastructure.temporal.client import TemporalClientFactory
from app.infrastructure.temporal.lifecycle import TemporalWorkerLifecycle
from app.infrastructure.temporal.worker import (
    ActivityRegistry,
    TemporalWorkerFactory,
    WorkflowRegistry,
)
from app.kernel.container.di_container import DIContainer
from app.kernel.health.health import HealthRegistry
from app.kernel.registry.plugin import Plugin, PluginRegistry

if TYPE_CHECKING:
    from app.core.config import AppConfig


class InfrastructureContainer:
    """Wires all infrastructure components into the application DIContainer.

    Provides factory methods for creating and registering all infrastructure
    dependencies, organized by concern (database, redis, temporal, etc.).
    """

    def __init__(self, app_config: AppConfig) -> None:
        """Initialize with application configuration."""
        self._app_config = app_config
        self._container = DIContainer()

    @property
    def container(self) -> DIContainer:
        """Return the underlying DIContainer instance."""
        return self._container

    def setup(self) -> None:
        """Register all infrastructure components into the DI container."""
        self._register_configurations()
        self._register_database()
        self._register_redis()
        self._register_event_bus()
        self._register_temporal()
        self._register_plugins()
        self._register_health()
        self._register_observability()

    def _register_configurations(self) -> None:
        """Register configuration providers as singletons."""
        cfg = self._app_config

        database_config = DatabaseConfiguration(
            host=cfg.db_host,
            port=cfg.db_port,
            user=cfg.db_user,
            password=cfg.db_password,
            database=cfg.db_name,
            min_pool_size=cfg.db_min_pool_size,
            max_pool_size=cfg.db_max_pool_size,
        )
        redis_config = RedisConfiguration(
            host=cfg.redis_host,
            port=cfg.redis_port,
            db=cfg.redis_db,
        )
        temporal_config = TemporalConfiguration(
            host=cfg.temporal_host,
            port=cfg.temporal_port,
            namespace=cfg.temporal_namespace,
            task_queue=cfg.temporal_task_queue,
        )
        logging_config = LoggingConfiguration(
            level=cfg.app_log_level,
            json_format=cfg.env != "development",
        )

        self._container.register_singleton(
            DatabaseConfiguration,
            lambda _c: database_config,
        )
        self._container.register_singleton(
            RedisConfiguration,
            lambda _c: redis_config,
        )
        self._container.register_singleton(
            TemporalConfiguration,
            lambda _c: temporal_config,
        )
        self._container.register_singleton(
            LoggingConfiguration,
            lambda _c: logging_config,
        )

    def _register_database(self) -> None:
        """Register database infrastructure components."""
        self._container.register_singleton(
            DatabaseEngine,
            lambda c: DatabaseEngine(c.resolve(DatabaseConfiguration)),
        )
        self._container.register_singleton(
            SessionManager,
            lambda c: SessionManager(c.resolve(DatabaseEngine)),
        )
        self._container.register_factory(
            SqlAlchemyUnitOfWork,
            lambda c: SqlAlchemyUnitOfWork(
                c.resolve(DatabaseEngine).session_factory,
            ),
        )

    def _register_redis(self) -> None:
        """Register Redis client infrastructure."""
        self._container.register_singleton(
            AsyncRedis,
            lambda c: AsyncRedis(
                host=c.resolve(RedisConfiguration).host,
                port=c.resolve(RedisConfiguration).port,
                db=c.resolve(RedisConfiguration).db,
                decode_responses=True,
            ),
        )

    def _register_event_bus(self) -> None:
        """Register event bus infrastructure."""
        self._container.register_singleton(
            JsonEventSerializer,
            lambda _c: JsonEventSerializer(),
        )
        self._container.register_singleton(
            DeadLetterQueue,
            lambda c: DeadLetterQueue(
                redis=c.resolve(AsyncRedis),
                config=c.resolve(RedisConfiguration),
                serializer=c.resolve(JsonEventSerializer),
            ),
        )
        self._container.register_singleton(
            RedisStreamsEventBus,
            lambda c: RedisStreamsEventBus(
                redis=c.resolve(AsyncRedis),
                config=c.resolve(RedisConfiguration),
                serializer=c.resolve(JsonEventSerializer),
                dead_letter_queue=c.resolve(DeadLetterQueue),
            ),
        )

    def _register_temporal(self) -> None:
        """Register Temporal infrastructure components."""
        activity_registry = ActivityRegistry()
        activity_registry.register(create_run_activity)
        activity_registry.register(queue_run_activity)
        activity_registry.register(start_run_activity)
        activity_registry.register(update_progress_activity)
        activity_registry.register(complete_run_activity)
        activity_registry.register(fail_run_activity)
        activity_registry.register(cancel_run_activity)

        activity_registry.register(create_agent_run_activity)
        activity_registry.register(queue_agent_run_activity)
        activity_registry.register(start_agent_run_activity)
        activity_registry.register(update_agent_run_progress_activity)
        activity_registry.register(complete_agent_run_activity)
        activity_registry.register(fail_agent_run_activity)
        activity_registry.register(cancel_agent_run_activity)

        workflow_registry = WorkflowRegistry()
        workflow_registry.register(EvaluationRunWorkflow)
        workflow_registry.register(AgentRunWorkflow)

        self._container.register_singleton(
            ActivityRegistry,
            lambda _c: activity_registry,
        )
        self._container.register_singleton(
            WorkflowRegistry,
            lambda _c: workflow_registry,
        )
        self._container.register_singleton(
            TemporalClientFactory,
            lambda c: TemporalClientFactory(c.resolve(TemporalConfiguration)),
        )
        self._container.register_singleton(
            TemporalWorkerFactory,
            lambda c: TemporalWorkerFactory(
                config=c.resolve(TemporalConfiguration),
                activity_registry=c.resolve(ActivityRegistry),
                workflow_registry=c.resolve(WorkflowRegistry),
            ),
        )
        self._container.register_singleton(
            TemporalWorkerLifecycle,
            lambda c: TemporalWorkerLifecycle(
                worker_factory=c.resolve(TemporalWorkerFactory),
                client_factory=c.resolve(TemporalClientFactory),
                config=c.resolve(TemporalConfiguration),
            ),
        )

    def _register_plugins(self) -> None:
        """Register plugin infrastructure components."""
        self._container.register_singleton(
            PluginRegistry,
            lambda _c: PluginRegistry[Plugin](plugin_type="infrastructure"),
        )
        fs_discovery = FilesystemPluginDiscovery(
            plugin_dirs=[Path("app/plugins")],
        )
        ep_discovery = EntryPointPluginDiscovery()
        self._container.register_singleton(
            PluginLoaderImpl,
            lambda c: PluginLoaderImpl(
                registry=c.resolve(PluginRegistry),
                discovery_strategies=[fs_discovery, ep_discovery],
            ),
        )

    def _register_health(self) -> None:
        """Register health check infrastructure."""
        self._container.register_singleton(
            HealthRegistry,
            lambda _c: HealthRegistry(),
        )

    def _register_observability(self) -> None:
        """Register observability infrastructure."""
