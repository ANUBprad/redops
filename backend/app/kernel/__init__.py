"""RedOps Eval — Platform Kernel.

Every future bounded context depends on this layer.
No business logic lives here — only shared infrastructure contracts.

Public API:
    - container.DIContainer, Lifetime, Scope
    - events.EventBus, EventPublisher, BaseEvent, EventSerializer
    - results.Result, Success, Failure, map, bind
    - exceptions.* (full error hierarchy)
    - registry.Plugin, PluginRegistry, PluginMetadata, PluginContext, PluginLoader
    - repositories.UnitOfWork, Transaction
    - entities.Entity, AggregateRoot, DomainEvent, UUIDv7
    - lifecycle.LifecycleService
    - service_registry.ServiceRegistry
    - health.HealthRegistry, HealthContributor, HealthReport
    - contracts.* (BaseConfiguration, ServiceConfiguration)
"""

from app.kernel.container.di_container import DIContainer, Lifetime, Scope
from app.kernel.contracts.config import (
    BaseConfiguration,
    ServiceConfiguration,
)
from app.kernel.entities.base import (
    AggregateRoot,
    DomainEvent,
    Entity,
    UUIDv7,
)
from app.kernel.events.event_bus import (
    BaseEvent,
    EventBus,
    EventPublisher,
    EventSerializer,
)
from app.kernel.exceptions.errors import (
    BaseError,
    ConflictError,
    DependencyError,
    DomainError,
    InfrastructureError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.kernel.health.health import (
    HealthContributor,
    HealthRegistry,
    HealthResult,
    HealthStatus,
)
from app.kernel.lifecycle.lifecycle import (
    LifecycleService,
)
from app.kernel.registry.plugin import (
    Plugin,
    PluginContext,
    PluginLoader,
    PluginMetadata,
    PluginRegistry,
)
from app.kernel.repositories.unit_of_work import Transaction, UnitOfWork
from app.kernel.results.result import (
    Failure,
    Result,
    Success,
    bind,
    failure,
    is_failure,
    is_success,
    success,
)
from app.kernel.results.result import (
    map as map_result,
)
from app.kernel.service_registry.service_registry import ServiceRegistry

__all__ = [
    "AggregateRoot",
    "BaseConfiguration",
    "BaseError",
    "BaseEvent",
    "ConflictError",
    "DIContainer",
    "DependencyError",
    "DomainError",
    "DomainEvent",
    "Entity",
    "EventBus",
    "EventPublisher",
    "EventSerializer",
    "Failure",
    "HealthContributor",
    "HealthRegistry",
    "HealthResult",
    "HealthStatus",
    "InfrastructureError",
    "LifecycleService",
    "Lifetime",
    "NotFoundError",
    "Plugin",
    "PluginContext",
    "PluginLoader",
    "PluginMetadata",
    "PluginRegistry",
    "Result",
    "Scope",
    "ServiceConfiguration",
    "ServiceRegistry",
    "Success",
    "Transaction",
    "UUIDv7",
    "UnauthorizedError",
    "UnitOfWork",
    "ValidationError",
    "bind",
    "failure",
    "is_failure",
    "is_success",
    "map_result",
    "success",
]
