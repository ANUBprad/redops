"""Report refresh service — invalidates cached analytics data on domain events.

Maintains an in-memory cache invalidation registry that tracks which
projects and evaluations have stale data. Downstream consumers
(dashboards, reports, API endpoints) can query the registry to
determine if cached data needs recomputation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock

from structlog import get_logger

logger = get_logger("redops_eval.report_refresh")


@dataclass(frozen=True, slots=True)
class InvalidationEntry:
    """A single cache invalidation record."""

    entity_type: str
    entity_id: str
    invalidated_at: datetime
    reason: str


class ReportRefreshService:
    """Service for tracking and invalidating stale analytics data.

    When domain events arrive (evaluation completed, finding detected,
    etc.), the service records invalidation entries for affected
    projects and evaluations. Downstream consumers check
    ``is_stale()`` before serving cached data.
    """

    def __init__(self) -> None:
        self._invalidations: list[InvalidationEntry] = []
        self._lock = Lock()

    def invalidate(self, entity_type: str, entity_id: str, reason: str) -> None:
        """Record a cache invalidation for an entity."""
        entry = InvalidationEntry(
            entity_type=entity_type,
            entity_id=entity_id,
            invalidated_at=datetime.now(UTC),
            reason=reason,
        )
        with self._lock:
            self._invalidations.append(entry)
        logger.debug(
            "Cache invalidated",
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
        )

    def is_stale(self, entity_type: str, entity_id: str) -> bool:
        """Check if an entity has been invalidated since last check."""
        with self._lock:
            for entry in reversed(self._invalidations):
                if entry.entity_type == entity_type and entry.entity_id == entity_id:
                    return True
        return False

    def get_invalidations(
        self,
        entity_type: str | None = None,
        since: datetime | None = None,
    ) -> list[InvalidationEntry]:
        """Retrieve invalidation entries with optional filters."""
        with self._lock:
            entries = list(self._invalidations)
        if entity_type is not None:
            entries = [e for e in entries if e.entity_type == entity_type]
        if since is not None:
            entries = [e for e in entries if e.invalidated_at >= since]
        return entries

    def clear(self, entity_type: str | None = None, entity_id: str | None = None) -> int:
        """Clear invalidation entries. Returns the count removed."""
        with self._lock:
            before = len(self._invalidations)
            if entity_type is None and entity_id is None:
                self._invalidations.clear()
            else:
                self._invalidations = [
                    e
                    for e in self._invalidations
                    if not (
                        (entity_type is None or e.entity_type == entity_type)
                        and (entity_id is None or e.entity_id == entity_id)
                    )
                ]
            return before - len(self._invalidations)
