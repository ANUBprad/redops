"""Audit event subscriber — persists domain events as audit log entries.

Consumes domain events from the EventBus and converts them into
AuditLog entries through the existing AuditService, providing an
immutable audit trail of all significant system actions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from structlog import get_logger

from app.audit.domain.entities import AuditAction, AuditResourceType

if TYPE_CHECKING:
    from app.audit.services.audit_service import AuditService

logger = get_logger("redops_eval.event_subscribers.audit")


_EVENT_AUDIT_MAP: dict[str, tuple[str, str]] = {
    "evaluation.created": (AuditAction.CREATE, AuditResourceType.EVALUATION),
    "evaluation.queued": (AuditAction.EXECUTE, AuditResourceType.EVALUATION),
    "evaluation.started": (AuditAction.EXECUTE, AuditResourceType.EVALUATION),
    "evaluation.completed": (AuditAction.EXECUTE, AuditResourceType.EVALUATION_RUN),
    "evaluation.cancelled": (AuditAction.CANCEL, AuditResourceType.EVALUATION_RUN),
    "evaluation.failed": (AuditAction.EXECUTE, AuditResourceType.EVALUATION_RUN),
    "evaluation.timed_out": (AuditAction.EXECUTE, AuditResourceType.EVALUATION_RUN),
    "evaluation.item.completed": (AuditAction.EXECUTE, AuditResourceType.EVALUATION_RUN),
    "evaluation.item.failed": (AuditAction.EXECUTE, AuditResourceType.EVALUATION_RUN),
    "evaluation.metric.computed": (AuditAction.EXECUTE, AuditResourceType.METRIC),
    "evaluation.checkpoint.created": (AuditAction.CREATE, AuditResourceType.EVALUATION_RUN),
    "safety.attack_run.created": (AuditAction.CREATE, AuditResourceType.ATTACK_RUN),
    "safety.attack_run.started": (AuditAction.EXECUTE, AuditResourceType.ATTACK_RUN),
    "safety.attack_run.completed": (AuditAction.EXECUTE, AuditResourceType.ATTACK_RUN),
    "safety.attack_run.failed": (AuditAction.EXECUTE, AuditResourceType.ATTACK_RUN),
    "safety.attack_run.cancelled": (AuditAction.CANCEL, AuditResourceType.ATTACK_RUN),
    "safety.finding.detected": (AuditAction.CREATE, AuditResourceType.RED_TEAM),
    "safety.campaign.completed": (AuditAction.EXECUTE, AuditResourceType.RED_TEAM),
}


class AuditEventSubscriber:
    """Subscribes to domain events and persists them as audit log entries.

    Each event is mapped to an AuditAction and AuditResourceType using
    the event_type string. Events not in the mapping are silently
    skipped to avoid noise from low-level events.
    """

    def __init__(self, audit_service: AuditService) -> None:
        self._audit_service = audit_service

    async def handle(self, event: Any) -> None:
        """Handle a domain event by recording an audit log entry."""
        event_type = getattr(event, "event_type", None)
        if event_type is None:
            return

        mapping = _EVENT_AUDIT_MAP.get(event_type)
        if mapping is None:
            return

        action, resource_type = mapping
        resource_id = self._extract_resource_id(event)
        correlation_id = getattr(event, "correlation_id", None)
        metadata = self._build_metadata(event, event_type)

        try:
            await self._audit_service.record(
                user_id="system",
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata=metadata,
                request_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "Failed to record audit log for event",
                event_type=event_type,
                resource_id=resource_id,
            )

    @staticmethod
    def _extract_resource_id(event: Any) -> str:
        for attr in ("run_id", "item_id", "definition_id", "finding_id", "campaign_id"):
            val = getattr(event, attr, None)
            if val is not None:
                return str(val)
        return ""

    @staticmethod
    def _build_metadata(event: Any, event_type: str) -> dict[str, object]:
        meta: dict[str, object] = {"event_type": event_type}
        for attr in (
            "items_total",
            "items_completed",
            "items_passed",
            "items_violated",
            "violation_count",
            "total_rounds",
            "error_code",
            "error_message",
            "metric_name",
            "score",
            "evaluation_name",
            "provider_name",
            "model_id",
        ):
            val = getattr(event, attr, None)
            if val is not None:
                meta[attr] = val
        return meta
