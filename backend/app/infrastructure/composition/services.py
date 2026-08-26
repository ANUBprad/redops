"""Service registration into the Kernel ServiceRegistry.

Maps infrastructure LifecycleService implementations to named
services with dependency declarations for topological startup
ordering. Also registers health contributors into the HealthRegistry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.agents.temporal.activities import (
    configure_agent_provider_registry,
    configure_agent_session_factory,
)
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.temporal.activities import (
    configure_cost_calculator,
    configure_metric_engine,
    configure_provider_registry,
    configure_session_factory,
)
from app.infrastructure.database.engine import DatabaseEngine
from app.infrastructure.event_bus.redis_event_bus import RedisStreamsEventBus
from app.infrastructure.health.database import DatabaseHealthContributor
from app.infrastructure.health.redis import RedisHealthContributor
from app.infrastructure.health.temporal import TemporalHealthContributor
from app.infrastructure.temporal.client import TemporalClientFactory
from app.infrastructure.temporal.lifecycle import TemporalWorkerLifecycle
from app.providers.cost.calculator import CostCalculator
from app.providers.registry.registry import ProviderRegistry
from app.redteam.temporal.activities import configure_redteam_provider_registry

if TYPE_CHECKING:
    from app.kernel.container.di_container import DIContainer
    from app.kernel.health.health import HealthRegistry
    from app.kernel.service_registry.service_registry import ServiceRegistry


class InfrastructureServices:
    """Registers all infrastructure services into the ServiceRegistry.

    Handles the mapping of infrastructure components to the Kernel's
    ServiceRegistry with proper dependency ordering and health check
    registration.
    """

    def __init__(
        self,
        di_container: DIContainer,
        service_registry: ServiceRegistry,
        health_registry: HealthRegistry,
    ) -> None:
        """Initialize with DI container and registries."""
        self._container = di_container
        self._service_registry = service_registry
        self._health_registry = health_registry

    def register_all(self) -> None:
        """Register all infrastructure services and health contributors."""
        self._register_database_services()
        self._register_evaluation_services()
        self._register_event_bus_services()
        self._register_temporal_services()
        self._register_health_contributors()

    def _register_database_services(self) -> None:
        """Register database lifecycle services and health."""
        engine = self._container.resolve(DatabaseEngine)
        configure_session_factory(engine.session_factory)
        configure_agent_session_factory(engine.session_factory)
        self._service_registry.register("database", engine)
        self._health_registry.register(DatabaseHealthContributor(engine))

    def _register_evaluation_services(self) -> None:
        """Configure evaluation dependencies for temporal activities.

        The provider registry, metric engine, and cost calculator
        are resolved from the DI container and shared with the
        Temporal item execution activities so the worker executes
        real provider calls with real cost estimation.
        """
        provider_registry = self._container.resolve(ProviderRegistry)
        metric_engine = self._container.resolve(MetricEngine)
        cost_calculator = self._container.resolve(CostCalculator)

        configure_provider_registry(provider_registry)
        configure_metric_engine(metric_engine)
        configure_cost_calculator(cost_calculator)

        configure_redteam_provider_registry(provider_registry)

        agent_provider_registry = self._container.resolve(ProviderRegistry)
        configure_agent_provider_registry(agent_provider_registry)

    def _register_event_bus_services(self) -> None:
        """Register event bus lifecycle services and health."""
        event_bus = self._container.resolve(RedisStreamsEventBus)
        redis_client = event_bus.redis

        self._service_registry.register(
            "event_bus",
            event_bus,
            depends_on=["database"],
        )
        self._health_registry.register(RedisHealthContributor(redis_client))

    def _register_temporal_services(self) -> None:
        """Register Temporal lifecycle services and health."""
        temporal_client = self._container.resolve(TemporalClientFactory)
        self._service_registry.register(
            "temporal_client",
            temporal_client,
            depends_on=["database"],
        )

        temporal_worker = self._container.resolve(TemporalWorkerLifecycle)
        self._service_registry.register(
            "temporal_worker",
            temporal_worker,
            depends_on=["temporal_client"],
        )
        self._health_registry.register(TemporalHealthContributor(temporal_client))

    def _register_health_contributors(self) -> None:
        """Ensure the health registry has all expected contributors.

        Individual health contributors are registered alongside their
        respective services.
        """
