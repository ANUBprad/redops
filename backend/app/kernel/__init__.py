"""RedOps Eval — Platform Kernel.

Every future bounded context depends on this layer.
No business logic lives here — only shared infrastructure contracts.

Public API:
    - container.DIContainer, Lifetime, Scope
    - events.EventBus, EventPublisher, EventSubscriber, BaseEvent, EventSerializer
    - results.Result, Success, Failure, map, bind
    - exceptions.* (full error hierarchy)
    - registry.Plugin, PluginRegistry, PluginMetadata, PluginContext, PluginLoader
    - repositories.Repository, ReadRepository, WriteRepository, UnitOfWork, Transaction, QueryOptions
    - entities.Entity, AggregateRoot, ValueObject, DomainEvent, UUIDv7
    - lifecycle.LifecycleService, LifecycleManager, LifecycleState
    - service_registry.ServiceRegistry
    - health.HealthRegistry, HealthContributor, HealthReport
    - contracts.* (BaseConfiguration, ServiceConfiguration, PluginConfiguration, EnvironmentConfiguration)
    - utils.* (Clock, UUIDGenerator, RetryPolicy, paginators, CircuitBreaker, AsyncLock)
"""

from app.kernel.container.di_container import DIContainer, Lifetime, Scope
from app.kernel.contracts.config import (
    BaseConfiguration,
    EnvironmentConfiguration,
    PluginConfiguration,
    ServiceConfiguration,
)
from app.kernel.entities.base import (
    AggregateRoot,
    DomainEvent,
    Entity,
    TimestampMixin,
    UUIDv7,
    ValueObject,
    VersionMixin,
    SoftDeleteMixin,
)
from app.kernel.events.event_bus import (
    BaseEvent,
    EventBus,
    EventPublisher,
    EventSerializer,
    EventSubscriber,
)
from app.kernel.exceptions.errors import (
    ApplicationError,
    BaseError,
    ConfigurationError,
    ConflictError,
    DependencyError,
    DomainError,
    ExternalServiceError,
    InfrastructureError,
    NotFoundError,
    TimeoutError,
    UnauthorizedError,
    ValidationError,
)
from app.kernel.health.health import (
    HealthContributor,
    HealthRegistry,
    HealthReport,
    HealthResult,
    HealthStatus,
)
from app.kernel.lifecycle.lifecycle import (
    LifecycleManager,
    LifecycleService,
    LifecycleState,
)
from app.kernel.registry.plugin import (
    Plugin,
    PluginContext,
    PluginLoader,
    PluginMetadata,
    PluginRegistry,
)
from app.kernel.repositories.repository import (
    QueryOptions,
    ReadRepository,
    Repository,
    WriteRepository,
)
from app.kernel.repositories.specification import (
    AndSpecification,
    NotSpecification,
    OrSpecification,
    Specification,
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
    map as map_result,
    success,
    unwrap,
    unwrap_or,
)
from app.kernel.service_registry.service_registry import ServiceRegistry
from app.kernel.utils.async_lock import AsyncLock
from app.kernel.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    InMemoryCircuitBreaker,
)
from app.kernel.utils.clock import Clock, FrozenClock, SystemClock
from app.kernel.utils.paginator import (
    CursorPage,
    CursorPaginator,
    CursorParams,
    Page,
    PageParams,
    Paginator,
)
from app.kernel.utils.retry import (
    BackoffPolicy,
    ExponentialBackoff,
    FixedBackoff,
    NoBackoff,
    RetryPolicy,
    with_retry,
)
from app.kernel.utils.uuid_generator import (
    RandomUUIDGenerator,
    SequentialUUIDGenerator,
    UUIDGenerator,
)

__all__ = [
    "DIContainer",
    "Lifetime",
    "Scope",
    "BaseConfiguration",
    "EnvironmentConfiguration",
    "PluginConfiguration",
    "ServiceConfiguration",
    "AggregateRoot",
    "DomainEvent",
    "Entity",
    "TimestampMixin",
    "UUIDv7",
    "ValueObject",
    "VersionMixin",
    "SoftDeleteMixin",
    "BaseEvent",
    "EventBus",
    "EventPublisher",
    "EventSerializer",
    "EventSubscriber",
    "ApplicationError",
    "BaseError",
    "ConfigurationError",
    "ConflictError",
    "DependencyError",
    "DomainError",
    "ExternalServiceError",
    "InfrastructureError",
    "NotFoundError",
    "TimeoutError",
    "UnauthorizedError",
    "ValidationError",
    "HealthContributor",
    "HealthRegistry",
    "HealthReport",
    "HealthResult",
    "HealthStatus",
    "LifecycleManager",
    "LifecycleService",
    "LifecycleState",
    "Plugin",
    "PluginContext",
    "PluginLoader",
    "PluginMetadata",
    "PluginRegistry",
    "QueryOptions",
    "ReadRepository",
    "Repository",
    "WriteRepository",
    "AndSpecification",
    "NotSpecification",
    "OrSpecification",
    "Specification",
    "Transaction",
    "UnitOfWork",
    "Failure",
    "Result",
    "Success",
    "bind",
    "failure",
    "is_failure",
    "is_success",
    "map_result",
    "success",
    "unwrap",
    "unwrap_or",
    "ServiceRegistry",
    "AsyncLock",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitState",
    "InMemoryCircuitBreaker",
    "Clock",
    "FrozenClock",
    "SystemClock",
    "CursorPage",
    "CursorPaginator",
    "CursorParams",
    "Page",
    "PageParams",
    "Paginator",
    "BackoffPolicy",
    "ExponentialBackoff",
    "FixedBackoff",
    "NoBackoff",
    "RetryPolicy",
    "with_retry",
    "RandomUUIDGenerator",
    "SequentialUUIDGenerator",
    "UUIDGenerator",
]
