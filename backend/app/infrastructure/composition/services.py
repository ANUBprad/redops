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
from app.analytics.temporal.activities import (
    configure_export_session_factory,
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
from app.infrastructure.event_bus.subscribers.audit_subscriber import AuditEventSubscriber
from app.infrastructure.event_bus.subscribers.notification_subscriber import (
    NotificationEventSubscriber,
)
from app.infrastructure.event_bus.subscribers.report_refresh_subscriber import (
    ReportRefreshSubscriber,
)
from app.infrastructure.event_bus.subscribers.webhook_subscriber import (
    WebhookDeliverySubscriber,
)
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


def _register_event_types(event_bus: RedisStreamsEventBus) -> None:
    """Register all known domain event types with the serializer.

    This ensures the JsonEventSerializer can deserialize events
    arriving from Redis Streams back into their concrete dataclass types.
    """
    from app.agents.domain.events.agent_events import (
        AgentCheckpointCreated,
        AgentCheckpointLoaded,
        AgentRunCancelled,
        AgentRunCompleted,
        AgentRunCreated,
        AgentRunFailed,
        AgentRunQueued,
        AgentRunStarted,
        AgentRunTimedOut,
        AgentStepCompleted,
        AgentStepFailed,
        AgentStepStarted,
    )
    from app.evaluation.domain.events.evaluation_events import (
        CheckpointCreated,
        CheckpointLoaded,
        EvaluationCancelled,
        EvaluationCompleted,
        EvaluationCreated,
        EvaluationFailed,
        EvaluationPaused,
        EvaluationQueued,
        EvaluationResumed,
        EvaluationStarted,
        EvaluationTimedOut,
        ItemCancelled,
        ItemCompleted,
        ItemFailed,
        ItemRetried,
        ItemSkipped,
        ItemStarted,
        MetricAggregated,
        MetricComputed,
        MetricFailed,
    )
    from app.redteam.domain.events import (
        AttackDefinitionActivated,
        AttackDefinitionArchived,
        AttackDefinitionCreated,
        AttackDefinitionUpdated,
        AttackRunCancelled,
        AttackRunCompleted,
        AttackRunCreated,
        AttackRunFailed,
        AttackRunQueued,
        AttackRunStarted,
        CampaignCompleted,
        FindingDetected,
    )

    serializer = event_bus._serializer
    for cls in (
        EvaluationCreated,
        EvaluationQueued,
        EvaluationStarted,
        EvaluationPaused,
        EvaluationResumed,
        EvaluationCompleted,
        EvaluationCancelled,
        EvaluationFailed,
        EvaluationTimedOut,
        ItemStarted,
        ItemCompleted,
        ItemFailed,
        ItemRetried,
        ItemCancelled,
        ItemSkipped,
        MetricComputed,
        MetricFailed,
        MetricAggregated,
        CheckpointCreated,
        CheckpointLoaded,
        AttackDefinitionCreated,
        AttackDefinitionUpdated,
        AttackDefinitionActivated,
        AttackDefinitionArchived,
        AttackRunCreated,
        AttackRunQueued,
        AttackRunStarted,
        AttackRunCompleted,
        AttackRunFailed,
        AttackRunCancelled,
        FindingDetected,
        CampaignCompleted,
        AgentRunCreated,
        AgentRunQueued,
        AgentRunStarted,
        AgentRunCompleted,
        AgentRunFailed,
        AgentRunCancelled,
        AgentRunTimedOut,
        AgentStepStarted,
        AgentStepCompleted,
        AgentStepFailed,
        AgentCheckpointCreated,
        AgentCheckpointLoaded,
    ):
        event_instance = cls()
        serializer.register_event_type(event_instance.event_type, cls)


def _subscribe_event_handlers(event_bus: RedisStreamsEventBus, di_container: DIContainer) -> None:
    """Create and subscribe all event handlers to the EventBus.

    Subscribers are registered BEFORE the event bus starts consuming,
    ensuring no events are missed during startup.
    """
    from app.analytics.services.report_refresh_service import ReportRefreshService
    from app.notification.providers.webhook_provider import WebhookNotificationProvider

    session_factory = di_container.resolve(DatabaseEngine).session_factory

    audit_subscriber = AuditEventSubscriber(session_factory)
    for event_type in (
        "evaluation.created",
        "evaluation.queued",
        "evaluation.started",
        "evaluation.completed",
        "evaluation.cancelled",
        "evaluation.failed",
        "evaluation.timed_out",
        "evaluation.item.completed",
        "evaluation.item.failed",
        "evaluation.metric.computed",
        "evaluation.checkpoint.created",
        "safety.attack_run.created",
        "safety.attack_run.started",
        "safety.attack_run.completed",
        "safety.attack_run.failed",
        "safety.attack_run.cancelled",
        "safety.finding.detected",
        "safety.campaign.completed",
    ):
        event_bus.subscribe(event_type, audit_subscriber.handle, group="audit")

    notif_subscriber = NotificationEventSubscriber(session_factory)
    event_bus.subscribe("evaluation.completed", notif_subscriber.handle, group="notifications")
    event_bus.subscribe("evaluation.failed", notif_subscriber.handle, group="notifications")
    event_bus.subscribe("safety.finding.detected", notif_subscriber.handle, group="notifications")
    event_bus.subscribe("safety.campaign.completed", notif_subscriber.handle, group="notifications")

    webhook_provider = WebhookNotificationProvider()
    webhook_subscriber = WebhookDeliverySubscriber(webhook_provider)
    event_bus.subscribe("evaluation.completed", webhook_subscriber.handle, group="webhooks")
    event_bus.subscribe("safety.campaign.completed", webhook_subscriber.handle, group="webhooks")
    event_bus.subscribe("safety.finding.detected", webhook_subscriber.handle, group="webhooks")

    report_refresh_service = ReportRefreshService()
    report_subscriber = ReportRefreshSubscriber(report_refresh_service)
    event_bus.subscribe("evaluation.completed", report_subscriber.handle, group="report_refresh")
    event_bus.subscribe("evaluation.failed", report_subscriber.handle, group="report_refresh")
    event_bus.subscribe(
        "evaluation.metric.computed", report_subscriber.handle, group="report_refresh"
    )
    event_bus.subscribe(
        "safety.attack_run.completed", report_subscriber.handle, group="report_refresh"
    )
    event_bus.subscribe("safety.finding.detected", report_subscriber.handle, group="report_refresh")
    event_bus.subscribe(
        "safety.campaign.completed", report_subscriber.handle, group="report_refresh"
    )


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
        self._populate_metric_definitions()
        self._register_event_bus_services()
        self._register_temporal_services()
        self._register_health_contributors()

    def _register_database_services(self) -> None:
        """Register database lifecycle services and health."""
        engine = self._container.resolve(DatabaseEngine)
        configure_session_factory(engine.session_factory)
        configure_agent_session_factory(engine.session_factory)
        configure_export_session_factory(engine.session_factory)
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

    def _populate_metric_definitions(self) -> None:
        """Populate the metric_definitions DB table at startup.

        Reads all definitions from the MetricRegistry and upserts
        them into the database for version traceability.
        """
        import asyncio

        from sqlalchemy import text

        from app.evaluation.metrics.registry import MetricRegistry
        from app.infrastructure.database.engine import DatabaseEngine

        metric_registry = self._container.resolve(MetricRegistry)
        engine = self._container.resolve(DatabaseEngine)

        records = metric_registry.to_db_records()
        if not records:
            return

        async def _upsert() -> None:
            async with engine.session_factory() as session:
                for record in records:
                    await session.execute(
                        text("""
                            INSERT INTO metric_definitions
                                (name, display_name, description, category, scale,
                                 version, evaluator_type, required_inputs, default_weight,
                                 direction, default_threshold, requires_context,
                                 plugin_module, tags, is_active, created_at, updated_at)
                            VALUES
                                (:name, :display_name, :description, :category, :scale,
                                 :version, :evaluator_type, :required_inputs, :default_weight,
                                 :direction, :default_threshold, :requires_context,
                                 :plugin_module, :tags, :is_active, NOW(), NOW())
                            ON CONFLICT (name) DO UPDATE SET
                                display_name = EXCLUDED.display_name,
                                description = EXCLUDED.description,
                                category = EXCLUDED.category,
                                scale = EXCLUDED.scale,
                                version = EXCLUDED.version,
                                evaluator_type = EXCLUDED.evaluator_type,
                                required_inputs = EXCLUDED.required_inputs,
                                default_weight = EXCLUDED.default_weight,
                                direction = EXCLUDED.direction,
                                default_threshold = EXCLUDED.default_threshold,
                                requires_context = EXCLUDED.requires_context,
                                plugin_module = EXCLUDED.plugin_module,
                                tags = EXCLUDED.tags,
                                is_active = EXCLUDED.is_active,
                                updated_at = NOW()
                        """),
                        record,
                    )
                await session.commit()

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Fire-and-forget during async startup; table population
                # happens in the background and errors are logged inside _upsert.
                _populate_task = loop.create_task(_upsert())  # noqa: RUF006
            else:
                loop.run_until_complete(_upsert())
        except RuntimeError:
            # No event loop running — safe to use run_until_complete
            asyncio.run(_upsert())

    def _register_event_bus_services(self) -> None:
        """Register event bus lifecycle services, event types, and subscribers.

        Event types are registered with the serializer so events can
        be deserialized from Redis Streams. Subscribers are registered
        before the event bus starts consuming.
        """
        event_bus = self._container.resolve(RedisStreamsEventBus)
        redis_client = event_bus.redis

        _register_event_types(event_bus)
        _subscribe_event_handlers(event_bus, self._container)

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
