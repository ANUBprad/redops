"""Application bootstrap orchestration.

Coordinates the initialization, startup, and shutdown of all
infrastructure components using the Kernel's lifecycle management
interfaces. Provides a unified bootstrap sequence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from structlog import get_logger

from app.infrastructure.composition.services import InfrastructureServices
from app.infrastructure.config.logging import LoggingConfiguration
from app.infrastructure.observability.logging import configure_infrastructure_logging
from app.kernel.health.health import HealthRegistry, HealthReport
from app.kernel.service_registry.service_registry import ServiceRegistry

if TYPE_CHECKING:
    from app.infrastructure.composition.container import InfrastructureContainer
    from app.kernel.container.di_container import DIContainer


class Bootstrap:
    """Orchestrates application bootstrap and shutdown sequences.

    Coordinates the initialization, startup, and shutdown of all
    infrastructure services using the Kernel's ServiceRegistry
    and HealthRegistry for lifecycle management and health reporting.
    """

    def __init__(self, container: InfrastructureContainer) -> None:
        """Initialize with the infrastructure DI container."""
        self._container = container
        self._di_container: DIContainer = container.container
        self._service_registry = ServiceRegistry()
        self._health_registry = HealthRegistry()
        self._initialized = False

    @property
    def di_container(self) -> DIContainer:
        """Return the configured DI container."""
        return self._di_container

    @property
    def service_registry(self) -> ServiceRegistry:
        """Return the service registry."""
        return self._service_registry

    @property
    def health_registry(self) -> HealthRegistry:
        """Return the health registry for readiness probes."""
        return self._health_registry

    async def initialize(self) -> None:
        """Initialize all infrastructure components.

        Order:
        1. Configure logging
        2. Register all DI components
        3. Register all services with dependency ordering
        4. Initialize the DI container
        """
        logging_config = self._di_container.resolve(LoggingConfiguration)
        configure_infrastructure_logging(logging_config)

        self._service_registry = ServiceRegistry()
        self._health_registry = HealthRegistry()

        services = InfrastructureServices(
            di_container=self._di_container,
            service_registry=self._service_registry,
            health_registry=self._health_registry,
        )
        services.register_all()

        self._initialized = True
        logger = get_logger("redops_eval.bootstrap")
        logger.info("Infrastructure initialized")

    async def start(self) -> None:
        """Start all registered services in dependency order."""
        if not self._initialized:
            await self.initialize()

        logger = get_logger("redops_eval.bootstrap")
        logger.info("Starting infrastructure services")

        await self._service_registry.start_all()

        logger.info("Infrastructure services started")

    async def stop(self) -> None:
        """Stop all registered services in reverse dependency order."""
        logger = get_logger("redops_eval.bootstrap")
        logger.info("Stopping infrastructure services")

        await self._service_registry.stop_all()

        logger.info("Infrastructure services stopped")

    async def health_check(self) -> HealthReport:
        """Run a full health check across all registered contributors.

        Returns:
            An aggregated HealthReport.

        """
        return await self._health_registry.check_all()
