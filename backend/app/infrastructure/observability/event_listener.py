"""SQLAlchemy event listener that captures run lifecycle events.

Listens for after_flush on the sync engine and detects status
changes on EvaluationRunModel, emitting timeline entries.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import event
from sqlalchemy import inspect as sa_inspect

from app.evaluation.domain.enums.evaluation_enums import RunStatus
from app.evaluation.observability.broadcaster import get_broadcaster
from app.evaluation.observability.domain import TimelineEntry
from app.infrastructure.database.models.attack_run import AttackRunModel
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel
from app.infrastructure.database.models.run_event import RunEventModel
from app.kernel.entities.base import UUIDv7

logger = logging.getLogger(__name__)

_EVENT_MAP: dict[str, str] = {
    RunStatus.CREATED.value: "evaluation.created",
    RunStatus.QUEUED.value: "evaluation.queued",
    RunStatus.STARTING.value: "evaluation.starting",
    RunStatus.RUNNING.value: "evaluation.started",
    RunStatus.COMPLETED.value: "evaluation.completed",
    RunStatus.FAILED.value: "evaluation.failed",
    RunStatus.CANCELLED.value: "evaluation.cancelled",
    RunStatus.TIMEDOUT.value: "evaluation.timed_out",
    RunStatus.PAUSED.value: "evaluation.paused",
    RunStatus.CANCELLING.value: "evaluation.cancelling",
}

_ATTACK_EVENT_MAP: dict[str, str] = {
    "created": "attack.created",
    "queued": "attack.queued",
    "starting": "attack.starting",
    "running": "attack.started",
    "completed": "attack.completed",
    "failed": "attack.failed",
    "cancelled": "attack.cancelled",
}


def _extract_status_change(instance: Any) -> tuple[str | None, str | None]:
    try:
        insp = sa_inspect(instance)
        status_attr = getattr(insp.attrs, "status", None)
        if status_attr is None:
            return None, None
        hist = status_attr.history
        if not hist.has_changes():
            return None, None
        old = hist.deleted[0] if hist.deleted else None
        new = hist.added[0] if hist.added else None
        return old, new
    except Exception:
        return None, None


def _emit_timeline(
    session: Any,
    run_model: EvaluationRunModel,
    event_type: str,
    extra: dict[str, Any],
) -> None:
    run_id = UUIDv7.from_string(run_model.id)
    entry = TimelineEntry(run_id=run_id, event_type=event_type, data=extra)

    session.add(
        RunEventModel(
            id=str(entry.entry_id),
            run_id=str(entry.run_id),
            event_type=entry.event_type,
            data=entry.data,
            correlation_id=entry.correlation_id,
            occurred_at=entry.occurred_at,
        ),
    )

    try:
        asyncio.create_task(  # noqa: RUF006
            get_broadcaster().publish(
                str(entry.run_id),
                {
                    "event_type": entry.event_type,
                    "occurred_at": entry.occurred_at.isoformat(),
                    "data": entry.data,
                },
            ),
        )
    except Exception:
        pass


def _emit_attack_timeline(
    session: Any,
    run_model: AttackRunModel,
    event_type: str,
    extra: dict[str, Any],
) -> None:
    entry = TimelineEntry(
        run_id=UUIDv7.from_string(run_model.id), event_type=event_type, data=extra
    )
    session.add(
        RunEventModel(
            id=str(entry.entry_id),
            run_id=str(entry.run_id),
            event_type=entry.event_type,
            data=entry.data,
            correlation_id=entry.correlation_id,
            occurred_at=entry.occurred_at,
        ),
    )
    try:
        asyncio.create_task(  # noqa: RUF006
            get_broadcaster().publish(
                str(entry.run_id),
                {
                    "event_type": entry.event_type,
                    "occurred_at": entry.occurred_at.isoformat(),
                    "data": entry.data,
                },
            ),
        )
    except Exception:
        pass


def _register_flush_listener(sync_engine: Any) -> None:
    @event.listens_for(sync_engine, "after_flush")
    def on_after_flush(session: Any, flush_context: Any) -> None:
        try:
            for instance in list(session.dirty):
                if isinstance(instance, EvaluationRunModel):
                    old_status, new_status = _extract_status_change(instance)
                    if not new_status or old_status == new_status:
                        continue
                    event_type = _EVENT_MAP.get(new_status)
                    if event_type is None:
                        continue
                    extra: dict[str, Any] = {}
                    if instance.failure_reason:
                        extra["failure_reason"] = instance.failure_reason
                    if instance.items_completed > 0:
                        extra["items_completed"] = instance.items_completed
                    if instance.items_total > 0:
                        extra["items_total"] = instance.items_total
                    _emit_timeline(session, instance, event_type, extra)

                elif isinstance(instance, AttackRunModel):
                    old_status, new_status = _extract_status_change(instance)
                    if not new_status or old_status == new_status:
                        continue
                    event_type = _ATTACK_EVENT_MAP.get(new_status)
                    if event_type is None:
                        continue
                    attack_extra: dict[str, Any] = {
                        "items_completed": instance.items_completed,
                        "items_total": instance.items_total,
                    }
                    _emit_attack_timeline(session, instance, event_type, attack_extra)

            for instance in list(session.new):
                if isinstance(instance, EvaluationRunModel):
                    st = instance.status or RunStatus.CREATED.value
                    event_type = _EVENT_MAP.get(st, "evaluation.created")
                    new_extra: dict[str, Any] = {}
                    if instance.items_total > 0:
                        new_extra["items_total"] = instance.items_total
                    _emit_timeline(session, instance, event_type, new_extra)

                elif isinstance(instance, AttackRunModel):
                    st = instance.status or "created"
                    event_type = _ATTACK_EVENT_MAP.get(st, "attack.created")
                    _emit_attack_timeline(
                        session,
                        instance,
                        event_type,
                        {"items_total": instance.items_total},
                    )

        except Exception:
            logger.exception("Error in run event listener")
            raise
