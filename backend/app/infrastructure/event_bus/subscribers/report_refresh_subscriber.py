"""Report refresh event subscriber — triggers cache invalidation on domain events.

Consumes domain events from the EventBus and invalidates stale
analytics data via the ReportRefreshService so downstream
consumers (dashboards, reports) recompute from fresh data.
"""

from __future__ import annotations

from typing import Any

from structlog import get_logger

from app.analytics.services.report_refresh_service import ReportRefreshService

logger = get_logger("redops_eval.event_subscribers.report_refresh")


_INVALIDATION_RULES: dict[str, tuple[str, str]] = {
    "evaluation.completed": ("evaluation", "Evaluation completed — report data stale"),
    "evaluation.failed": ("evaluation", "Evaluation failed — report data stale"),
    "evaluation.cancelled": ("evaluation", "Evaluation cancelled — report data stale"),
    "evaluation.metric.computed": ("evaluation", "Metric computed — report data stale"),
    "safety.attack_run.completed": ("attack_run", "Attack run completed — safety data stale"),
    "safety.attack_run.failed": ("attack_run", "Attack run failed — safety data stale"),
    "safety.finding.detected": ("finding", "Finding detected — safety data stale"),
    "safety.campaign.completed": ("campaign", "Campaign completed — safety data stale"),
}


class ReportRefreshSubscriber:
    """Subscribes to domain events and invalidates report caches.

    Maps selected domain events to cache invalidation calls on the
    ReportRefreshService. Events not in the rules mapping are silently
    skipped.
    """

    def __init__(self, report_refresh_service: ReportRefreshService) -> None:
        self._service = report_refresh_service

    async def handle(self, event: Any) -> None:
        """Handle a domain event by invalidating relevant caches."""
        event_type = getattr(event, "event_type", None)
        if event_type is None:
            return

        rule = _INVALIDATION_RULES.get(event_type)
        if rule is None:
            return

        entity_type, reason = rule
        entity_id = self._extract_entity_id(event)

        try:
            self._service.invalidate(entity_type, entity_id, reason)
        except Exception:
            logger.exception(
                "Failed to invalidate report cache",
                event_type=event_type,
                entity_id=entity_id,
            )

    @staticmethod
    def _extract_entity_id(event: Any) -> str:
        for attr in ("run_id", "item_id", "finding_id", "campaign_id"):
            val = getattr(event, attr, None)
            if val is not None:
                return str(val)
        return ""
