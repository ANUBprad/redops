from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import pytest

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
from app.kernel.lifecycle.lifecycle import LifecycleService
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
    Success,
    bind,
    failure,
    is_failure,
    is_success,
    success,
    unwrap,
    unwrap_or,
)
from app.kernel.results.result import (
    map as map_result,
)
from app.kernel.service_registry.service_registry import ServiceRegistry

# ──────────────────────────────────────────────
# 1. DI Container Tests
# ──────────────────────────────────────────────


class _TestService(ABC):
    @abstractmethod
    def value(self) -> str: ...


class _ConcreteService(_TestService):
    def __init__(self, name: str = "default") -> None:
        self.name = name

    def value(self) -> str:
        return f"service-{self.name}"


class _DisposableService:
    def __init__(self) -> None:
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


class TestDIContainer:
    def test_register_and_resolve_singleton(self) -> None:
        container = DIContainer()
        container.register_singleton(_TestService, lambda c: _ConcreteService())

        instance1 = container.resolve(_TestService)
        instance2 = container.resolve(_TestService)

        assert instance1 is instance2
        assert instance1.value() == "service-default"

    def test_register_and_resolve_transient(self) -> None:
        container = DIContainer()
        container.register_factory(_TestService, lambda c: _ConcreteService())

        instance1 = container.resolve(_TestService)
        instance2 = container.resolve(_TestService)

        assert instance1 is not instance2

    def test_resolve_scoped(self) -> None:
        container = DIContainer()
        container.register(
            _TestService,
            lambda c: _ConcreteService("scoped"),
            lifetime=Lifetime.SCOPED,
        )

        scope = Scope()
        instance1 = container.resolve(_TestService, scope=scope)
        instance2 = container.resolve(_TestService, scope=scope)
        assert instance1 is instance2

    def test_scoped_isolation(self) -> None:
        container = DIContainer()
        container.register(
            _TestService,
            lambda c: _ConcreteService("scoped"),
            lifetime=Lifetime.SCOPED,
        )

        scope1 = Scope()
        scope2 = Scope()

        instance_a = container.resolve(_TestService, scope=scope1)
        instance_b = container.resolve(_TestService, scope=scope2)

        assert instance_a is not instance_b

    def test_resolve_raises_on_unregistered(self) -> None:
        container = DIContainer()
        with pytest.raises(DependencyError, match="No registration found"):
            container.resolve(int)

    def test_scoped_requires_scope(self) -> None:
        container = DIContainer()
        container.register(
            _TestService,
            lambda c: _ConcreteService(),
            lifetime=Lifetime.SCOPED,
        )
        with pytest.raises(DependencyError, match="without a Scope"):
            container.resolve(_TestService)

    def test_is_registered(self) -> None:
        container = DIContainer()
        assert not container.is_registered(_TestService)
        container.register_singleton(_TestService, lambda c: _ConcreteService())
        assert container.is_registered(_TestService)

    def test_clear(self) -> None:
        container = DIContainer()
        container.register_singleton(_TestService, lambda c: _ConcreteService())
        container.clear()
        assert not container.is_registered(_TestService)

    def test_singleton_thread_safety(self) -> None:
        container = DIContainer()
        container.register_singleton(_TestService, lambda c: _ConcreteService())

        async def resolve_in_task() -> _TestService:
            return container.resolve(_TestService)

        async def run_concurrent() -> None:
            results = await asyncio.gather(*[resolve_in_task() for _ in range(10)])
            for i in range(1, 10):
                assert results[i] is results[0]

        asyncio.run(run_concurrent())

    def test_circular_dependency_detection(self) -> None:
        container = DIContainer()

        class A:
            pass

        class B:
            pass

        container.register_singleton(A, lambda c: A())
        container.register_singleton(B, lambda c: B())

        resolution_stack = container._resolution_stack  # type: ignore[attr-defined]
        resolution_stack.append(A)

        with pytest.raises(DependencyError, match="Circular dependency"):
            container.resolve(A)

        resolution_stack.clear()

    def test_dispose_clears_registrations(self) -> None:
        container = DIContainer()
        service = _DisposableService()
        container.register_singleton(_DisposableService, lambda c: service)

        container.dispose()
        assert not container.is_registered(_DisposableService)

    def test_dispose_calls_instance_dispose(self) -> None:
        container = DIContainer()
        service = _DisposableService()
        container.register_singleton(_DisposableService, lambda c: service)

        container.resolve(_DisposableService)
        container.dispose()
        assert service.disposed


# ──────────────────────────────────────────────
# 2. Error Hierarchy Tests
# ──────────────────────────────────────────────


class TestErrors:
    def test_base_error_defaults(self) -> None:
        err = BaseError()
        assert err.error_code == "UNKNOWN_ERROR"
        assert err.details == {}
        assert not err.retryable
        assert err.http_status == 500

    def test_base_error_with_trace_id(self) -> None:
        err = BaseError("test", trace_id="trace-123")
        assert err.trace_id == "trace-123"

    def test_base_error_auto_trace_id(self) -> None:
        err = BaseError()
        assert err.trace_id is not None
        assert len(err.trace_id) > 0

    def test_dependency_error(self) -> None:
        err = DependencyError("Service not found", dependency_name="Database")
        assert err.error_code == "DEPENDENCY_ERROR"
        assert err.details["dependency"] == "Database"

    def test_domain_error(self) -> None:
        err = DomainError("Invalid state transition")
        assert err.error_code == "DOMAIN_ERROR"
        assert err.http_status == 400

    def test_validation_error(self) -> None:
        err = ValidationError("Email is invalid", field="email")
        assert err.error_code == "VALIDATION_ERROR"
        assert err.http_status == 422

    def test_not_found_error(self) -> None:
        err = NotFoundError("User not found", resource_type="User", resource_id="123")
        assert err.error_code == "NOT_FOUND"
        assert err.http_status == 404

    def test_conflict_error(self) -> None:
        err = ConflictError("Already exists")
        assert err.error_code == "CONFLICT"
        assert err.http_status == 409

    def test_unauthorized_error(self) -> None:
        err = UnauthorizedError("Not authenticated")
        assert err.error_code == "UNAUTHORIZED"
        assert err.http_status == 401

    def test_infrastructure_error(self) -> None:
        err = InfrastructureError("DB connection lost")
        assert err.error_code == "INFRASTRUCTURE_ERROR"
        assert err.retryable
        assert err.http_status == 503

    def test_error_chain_with_cause(self) -> None:
        cause = ValueError("Original cause")
        err = InfrastructureError("Wrapper error", cause=cause)
        assert err.__cause__ is cause


# ──────────────────────────────────────────────
# 3. Result Pattern Tests
# ──────────────────────────────────────────────


class TestResult:
    def test_success_creation(self) -> None:
        result = success(42)
        assert isinstance(result, Success)
        assert result.value == 42

    def test_failure_creation(self) -> None:
        error = DomainError("Something bad")
        result = failure(error)
        assert isinstance(result, Failure)
        assert result.error is error

    def test_is_success(self) -> None:
        assert is_success(success(1))
        assert not is_success(failure(DomainError("")))

    def test_is_failure(self) -> None:
        assert is_failure(failure(DomainError("")))
        assert not is_failure(success(1))

    def test_unwrap_success(self) -> None:
        assert unwrap(success(42)) == 42

    def test_unwrap_failure_raises(self) -> None:
        with pytest.raises(DomainError):
            unwrap(failure(DomainError("fail")))

    def test_unwrap_or_with_success(self) -> None:
        assert unwrap_or(success(42), 0) == 42

    def test_unwrap_or_with_failure(self) -> None:
        assert unwrap_or(failure(DomainError("")), 0) == 0

    def test_match_pattern(self) -> None:
        result: Any = success("hello")
        match result:
            case Success(value):
                assert value == "hello"
            case Failure():
                pytest.fail("Should not match Failure")

    def test_success_is_frozen(self) -> None:
        s = success(1)
        with pytest.raises(AttributeError):
            s.value = 2

    def test_failure_is_frozen(self) -> None:
        err = DomainError("test")
        f = failure(err)
        with pytest.raises(AttributeError):
            f.error = err

    def test_map_transforms_value(self) -> None:
        result = map_result(success(42), lambda x: x * 2)
        assert is_success(result)
        assert unwrap(result) == 84

    def test_map_preserves_failure(self) -> None:
        err = DomainError("fail")
        result = map_result(failure(err), lambda x: x * 2)
        assert is_failure(result)
        assert result.error is err

    def test_bind_chains_success(self) -> None:
        def double_if_positive(x: int) -> Success[int] | Failure[DomainError]:
            if x > 0:
                return success(x * 2)
            return failure(DomainError("not positive"))

        result = bind(success(5), double_if_positive)
        assert is_success(result)
        assert unwrap(result) == 10

    def test_bind_short_circuits_on_failure(self) -> None:
        err = DomainError("initial failure")
        result = bind(failure(err), lambda x: success(x * 2))
        assert is_failure(result)
        assert result.error is err


# ──────────────────────────────────────────────
# 4. Entity / Value Object / DomainEvent Tests
# ──────────────────────────────────────────────


class _TestEntity(Entity):
    def __init__(self, name: str = "", entity_id: UUIDv7 | None = None) -> None:
        super().__init__(entity_id=entity_id)
        self.name = name


class _TestAggregate(AggregateRoot):
    def __init__(self, entity_id: UUIDv7 | None = None) -> None:
        super().__init__(entity_id=entity_id)
        self._events_raised = 0

    def do_action(self) -> None:
        self._events_raised += 1
        self.raise_event(_TestDomainEvent())


class _TestDomainEvent(DomainEvent):
    @property
    def event_type(self) -> str:
        return "test.entity.action"


class TestUUIDv7:
    def test_generates_unique_ids(self) -> None:
        id1 = UUIDv7()
        id2 = UUIDv7()
        assert id1 != id2

    def test_from_string(self) -> None:
        uid = UUIDv7.from_string("550e8400-e29b-41d4-a716-446655440000")
        assert str(uid) == "550e8400-e29b-41d4-a716-446655440000"

    def test_equality(self) -> None:
        uid1 = UUIDv7.from_string("550e8400-e29b-41d4-a716-446655440000")
        uid2 = UUIDv7.from_string("550e8400-e29b-41d4-a716-446655440000")
        assert uid1 == uid2
        assert hash(uid1) == hash(uid2)

    def test_inequality(self) -> None:
        uid1 = UUIDv7()
        uid2 = UUIDv7()
        assert uid1 != uid2


class TestEntity:
    def test_entity_has_id(self) -> None:
        entity = _TestEntity()
        assert isinstance(entity.id, UUIDv7)

    def test_entity_equality_by_id(self) -> None:
        uid = UUIDv7()
        e1 = _TestEntity("Alice", entity_id=uid)
        e2 = _TestEntity("Bob", entity_id=uid)
        assert e1 == e2
        assert hash(e1) == hash(e2)

    def test_entity_inequality(self) -> None:
        e1 = _TestEntity("Alice")
        e2 = _TestEntity("Bob")
        assert e1 != e2

    def test_timestamp_mixin(self) -> None:
        entity = _TestEntity()
        assert isinstance(entity.created_at, datetime)
        assert isinstance(entity.updated_at, datetime)

    def test_touch_updates_timestamp(self) -> None:
        entity = _TestEntity()
        original = entity.updated_at
        entity.touch()
        assert entity.updated_at >= original


class TestAggregateRoot:
    def test_collect_events_empty_initially(self) -> None:
        agg = _TestAggregate()
        assert agg.collect_events() == []

    def test_raise_and_collect_events(self) -> None:
        agg = _TestAggregate()
        agg.do_action()
        agg.do_action()
        events = agg.collect_events()
        assert len(events) == 2
        assert all(isinstance(e, _TestDomainEvent) for e in events)

    def test_collect_clears_events(self) -> None:
        agg = _TestAggregate()
        agg.do_action()
        agg.collect_events()
        assert agg.collect_events() == []


class TestDomainEvent:
    def test_event_has_id_and_timestamp(self) -> None:
        event = _TestDomainEvent()
        assert isinstance(event.event_id, UUIDv7)
        assert isinstance(event.occurred_at, datetime)

    def test_event_type(self) -> None:
        event = _TestDomainEvent()
        assert event.event_type == "test.entity.action"

    def test_correlation_id(self) -> None:
        event = _TestDomainEvent(correlation_id="corr-123")
        assert event.correlation_id == "corr-123"

    def test_events_have_unique_ids(self) -> None:
        e1 = _TestDomainEvent()
        e2 = _TestDomainEvent()
        assert e1.event_id != e2.event_id


# ──────────────────────────────────────────────
# 5. Event Bus Contract Tests
# ──────────────────────────────────────────────


class TestEventBusContracts:
    def test_event_publisher_has_publish(self) -> None:
        methods = [m for m in dir(EventPublisher) if not m.startswith("_")]
        assert "publish" in methods
        assert "publish_many" in methods

    def test_event_bus_combines_all(self) -> None:
        assert issubclass(EventBus, EventPublisher)
        assert "start" in EventBus.__abstractmethods__
        assert "stop" in EventBus.__abstractmethods__
        assert "health" in EventBus.__abstractmethods__

    def test_base_event_protocol(self) -> None:
        event = _TestDomainEvent()
        base_event: BaseEvent = event
        assert base_event.event_type == "test.entity.action"

    def test_event_serializer_has_serialize_and_deserialize(self) -> None:
        methods = [m for m in dir(EventSerializer) if not m.startswith("_")]
        assert "serialize" in methods
        assert "deserialize" in methods


# ──────────────────────────────────────────────
# 6. Repository Contract Tests
# ──────────────────────────────────────────────


class TestRepositoryContracts:
    def test_unit_of_work_has_commit(self) -> None:
        assert "commit" in UnitOfWork.__abstractmethods__

    def test_unit_of_work_has_rollback(self) -> None:
        assert "rollback" in UnitOfWork.__abstractmethods__

    def test_transaction_has_begin(self) -> None:
        assert "begin" in Transaction.__abstractmethods__


# ──────────────────────────────────────────────
# 8. Service Registry Tests
# ──────────────────────────────────────────────


class _MockService(LifecycleService):
    def __init__(self) -> None:
        self.initialized = False
        self.started = False
        self.stopped = False
        self.disposed = False
        self._healthy = True

    async def initialize(self) -> None:
        self.initialized = True

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def dispose(self) -> None:
        self.disposed = True

    async def health(self) -> bool:
        return self._healthy

    def set_healthy(self, healthy: bool) -> None:
        self._healthy = healthy


class TestServiceRegistry:
    @pytest.mark.asyncio
    async def test_register_and_start_all(self) -> None:
        registry = ServiceRegistry()
        service = _MockService()
        registry.register("test", service)
        await registry.start_all()
        assert service.started

    @pytest.mark.asyncio
    async def test_stop_all(self) -> None:
        registry = ServiceRegistry()
        service = _MockService()
        registry.register("test", service)
        await registry.start_all()
        await registry.stop_all()
        assert service.stopped

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        registry = ServiceRegistry()
        healthy = _MockService()
        unhealthy = _MockService()
        unhealthy.set_healthy(False)

        registry.register("healthy", healthy)
        registry.register("unhealthy", unhealthy)

        result = await registry.check_health()
        assert result["healthy"] is True
        assert result["unhealthy"] is False

    @pytest.mark.asyncio
    async def test_health_report(self) -> None:
        registry = ServiceRegistry()
        healthy = _MockService()
        registry.register("healthy", healthy)
        report = await registry.health_report()
        assert report["healthy"]["healthy"] is True
        assert report["healthy"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_start_order_respects_dependencies(self) -> None:
        registry = ServiceRegistry()
        started_order: list[str] = []

        class TrackingService(_MockService):
            def __init__(self, name: str) -> None:
                super().__init__()
                self._name = name

            async def start(self) -> None:
                started_order.append(self._name)
                await super().start()

        db = TrackingService("db")
        cache = TrackingService("cache")
        api = TrackingService("api")

        registry.register("api", api, depends_on=["db", "cache"])
        registry.register("db", db)
        registry.register("cache", cache)

        await registry.start_all()
        assert started_order.index("db") < started_order.index("api")
        assert started_order.index("cache") < started_order.index("api")

    def test_duplicate_registration_raises(self) -> None:
        registry = ServiceRegistry()
        registry.register("test", _MockService())
        with pytest.raises(ValueError, match="already registered"):
            registry.register("test", _MockService())

    def test_get_service(self) -> None:
        registry = ServiceRegistry()
        service = _MockService()
        registry.register("test", service)
        assert registry.get_service("test") is service
        assert registry.get_service("nonexistent") is None


# ──────────────────────────────────────────────
# 10. Plugin Registry Tests
# ──────────────────────────────────────────────


class _MockPlugin(Plugin):
    def __init__(self, name: str = "test-plugin") -> None:
        self._meta = PluginMetadata(name=name, version="1.0.0", plugin_type="test")
        self.initialized = False
        self.shutdown_called = False
        self._validation_issues: list[str] = []

    def metadata(self) -> PluginMetadata:
        return self._meta

    async def initialize(self, context: PluginContext | None = None) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.shutdown_called = True

    async def health(self) -> bool:
        return True

    async def validate(self) -> list[str]:
        return self._validation_issues


class TestPluginRegistry:
    @pytest.mark.asyncio
    async def test_register_and_initialize(self) -> None:
        registry = PluginRegistry[_MockPlugin]()
        plugin = _MockPlugin()
        registry.register(plugin)
        results = await registry.initialize_all()
        assert plugin.initialized
        assert results == [("test-plugin", True)]

    @pytest.mark.asyncio
    async def test_shutdown_all(self) -> None:
        registry = PluginRegistry[_MockPlugin]()
        plugin = _MockPlugin()
        registry.register(plugin)
        await registry.initialize_all()
        await registry.shutdown_all()
        assert plugin.shutdown_called

    def test_get_registered_plugin(self) -> None:
        registry = PluginRegistry[_MockPlugin]()
        plugin = _MockPlugin("my-plugin")
        registry.register(plugin)
        assert registry.get("my-plugin") is plugin
        assert registry.get("nonexistent") is None

    def test_get_all(self) -> None:
        registry = PluginRegistry[_MockPlugin]()
        registry.register(_MockPlugin("a"))
        registry.register(_MockPlugin("b"))
        assert len(registry.get_all()) == 2

    def test_duplicate_registration_raises(self) -> None:
        registry = PluginRegistry[_MockPlugin]()
        registry.register(_MockPlugin("dup"))
        with pytest.raises(ValueError, match="already registered"):
            registry.register(_MockPlugin("dup"))

    def test_list_metadata(self) -> None:
        registry = PluginRegistry[_MockPlugin]()
        registry.register(_MockPlugin("p1"))
        registry.register(_MockPlugin("p2"))
        metadata = registry.list_metadata()
        names = {m.name for m in metadata}
        assert names == {"p1", "p2"}

    def test_count(self) -> None:
        registry = PluginRegistry[_MockPlugin]()
        assert registry.count == 0
        registry.register(_MockPlugin("a"))
        assert registry.count == 1

    @pytest.mark.asyncio
    async def test_validate_all(self) -> None:
        registry = PluginRegistry[_MockPlugin]()
        plugin = _MockPlugin("valid")
        registry.register(plugin)
        results = await registry.validate_all()
        assert results["valid"] == []

    @pytest.mark.asyncio
    async def test_validate_with_issues(self) -> None:
        registry = PluginRegistry[_MockPlugin]()
        plugin = _MockPlugin("broken")
        plugin._validation_issues = ["missing config"]
        registry.register(plugin)
        results = await registry.validate_all()
        assert results["broken"] == ["missing config"]

    def test_plugin_context(self) -> None:
        ctx = PluginContext(plugin_name="test", plugin_type="metrics", config={"key": "val"})
        assert ctx.plugin_name == "test"
        assert ctx.plugin_type == "metrics"
        assert ctx.config == {"key": "val"}

    def test_plugin_loader_is_abstract(self) -> None:
        assert "discover_plugins" in PluginLoader.__abstractmethods__
        assert "load_plugin" in PluginLoader.__abstractmethods__


# ──────────────────────────────────────────────
# 11. Health Framework Tests
# ──────────────────────────────────────────────


class _MockHealthContributor(HealthContributor):
    def __init__(self, name: str, healthy: bool = True) -> None:
        self._name = name
        self._healthy = healthy

    async def check_health(self) -> HealthResult:
        return HealthResult(
            name=self._name,
            status=HealthStatus.HEALTHY if self._healthy else HealthStatus.UNHEALTHY,
            detail="ok" if self._healthy else "fail",
        )

    @property
    def contributor_name(self) -> str:
        return self._name


class TestHealthRegistry:
    @pytest.mark.asyncio
    async def test_all_healthy(self) -> None:
        registry = HealthRegistry()
        registry.register(_MockHealthContributor("db", True))
        registry.register(_MockHealthContributor("cache", True))
        report = await registry.check_all()
        assert report.all_healthy
        assert report.status is HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_degraded_when_one_fails(self) -> None:
        registry = HealthRegistry()
        registry.register(_MockHealthContributor("db", True))
        registry.register(_MockHealthContributor("cache", False))
        report = await registry.check_all()
        assert not report.all_healthy
        assert report.status is HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_empty_registry(self) -> None:
        registry = HealthRegistry()
        report = await registry.check_all()
        assert report.all_healthy
        assert len(report.checks) == 0

    def test_register_and_unregister(self) -> None:
        registry = HealthRegistry()
        contributor = _MockHealthContributor("test")
        registry.register(contributor)
        assert registry.contributor_count == 1
        registry.unregister("test")
        assert registry.contributor_count == 0

    def test_health_result_property(self) -> None:
        healthy = HealthResult(name="x", status=HealthStatus.HEALTHY)
        unhealthy = HealthResult(name="x", status=HealthStatus.UNHEALTHY)
        assert healthy.is_healthy
        assert not unhealthy.is_healthy


# ──────────────────────────────────────────────
# 12. Configuration Contract Tests
# ──────────────────────────────────────────────


class TestConfigContracts:
    def test_service_configuration(self) -> None:
        config = ServiceConfiguration(host="localhost", port=5432)
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.timeout_seconds == 30.0

    def test_service_configuration_is_immutable(self) -> None:
        config = ServiceConfiguration(host="localhost", port=5432)
        with pytest.raises(AttributeError):
            config.host = "other"

    def test_base_configuration(self) -> None:
        assert issubclass(ServiceConfiguration, BaseConfiguration)
