"""Scheduling domain entities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.kernel.entities.base import AggregateRoot, UUIDv7, VersionMixin


class ScheduleType(StrEnum):
    """Types of scheduled tasks."""

    EVALUATION = "evaluation"
    REGRESSION_SUITE = "regression_suite"
    BENCHMARK = "benchmark"
    RED_TEAM = "red_team"
    REPORT = "report"
    CLEANUP = "cleanup"


class ScheduleStatus(StrEnum):
    """Status of a schedule."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class RetryStrategy(StrEnum):
    """Retry strategies."""

    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry policy for failed schedule runs."""

    max_retries: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay_seconds: int = 60
    max_delay_seconds: int = 3600
    retryable_errors: tuple[str, ...] = ()

    def delay_for_attempt(self, attempt: int) -> int:
        """Calculate delay in seconds for a given attempt (1-based)."""
        if attempt <= 0:
            return 0
        if self.strategy == RetryStrategy.FIXED:
            delay = self.base_delay_seconds
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay_seconds * attempt
        else:  # exponential
            delay = self.base_delay_seconds * (2 ** (attempt - 1))
        return min(delay, self.max_delay_seconds)


@dataclass(frozen=True, slots=True)
class ConcurrencyConfig:
    """Concurrency configuration for schedules."""

    max_concurrent: int = 1
    queue_size: int = 10
    timeout_seconds: int = 3600


class Schedule(AggregateRoot, VersionMixin):
    """Schedule aggregate root for recurring tasks."""

    def __init__(
        self,
        *,
        entity_id: UUIDv7 | None = None,
        name: str,
        schedule_type: ScheduleType,
        cron_expression: str,
        task_config: dict[str, object] | None = None,
        organization_id: str | None = None,
        project_id: str | None = None,
        created_by: str | None = None,
        retry_policy: RetryPolicy | None = None,
        concurrency: ConcurrencyConfig | None = None,
        timezone: str = "UTC",
        status: ScheduleStatus = ScheduleStatus.ACTIVE,
        last_run_at: datetime | None = None,
        next_run_at: datetime | None = None,
        run_count: int = 0,
        failure_count: int = 0,
    ) -> None:
        super().__init__(entity_id=entity_id)
        VersionMixin.__init__(self)
        self._name = name.strip()
        self._schedule_type = schedule_type
        self._cron_expression = cron_expression.strip()
        self._task_config = task_config or {}
        self._organization_id = organization_id
        self._project_id = project_id
        self._created_by = created_by
        self._retry_policy = retry_policy or RetryPolicy()
        self._concurrency = concurrency or ConcurrencyConfig()
        self._timezone = timezone
        self._status = status
        self._last_run_at = last_run_at
        self._next_run_at = next_run_at
        self._run_count = run_count
        self._failure_count = failure_count

    @property
    def name(self) -> str:
        return self._name

    @property
    def schedule_type(self) -> ScheduleType:
        return self._schedule_type

    @property
    def cron_expression(self) -> str:
        return self._cron_expression

    @property
    def task_config(self) -> dict[str, object]:
        return self._task_config

    @property
    def organization_id(self) -> str | None:
        return self._organization_id

    @property
    def project_id(self) -> str | None:
        return self._project_id

    @property
    def created_by(self) -> str | None:
        return self._created_by

    @property
    def retry_policy(self) -> RetryPolicy:
        return self._retry_policy

    @property
    def concurrency(self) -> ConcurrencyConfig:
        return self._concurrency

    @property
    def timezone(self) -> str:
        return self._timezone

    @property
    def status(self) -> ScheduleStatus:
        return self._status

    @property
    def last_run_at(self) -> datetime | None:
        return self._last_run_at

    @property
    def next_run_at(self) -> datetime | None:
        return self._next_run_at

    @property
    def run_count(self) -> int:
        return self._run_count

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def is_active(self) -> bool:
        return self._status == ScheduleStatus.ACTIVE

    @classmethod
    def create(
        cls,
        *,
        name: str,
        schedule_type: ScheduleType,
        cron_expression: str,
        task_config: dict[str, object] | None = None,
        organization_id: str | None = None,
        project_id: str | None = None,
        created_by: str | None = None,
        retry_policy: RetryPolicy | None = None,
        concurrency: ConcurrencyConfig | None = None,
        timezone: str = "UTC",
    ) -> Schedule:
        validate_cron(cron_expression)
        return cls(
            name=name,
            schedule_type=schedule_type,
            cron_expression=cron_expression,
            task_config=task_config,
            organization_id=organization_id,
            project_id=project_id,
            created_by=created_by,
            retry_policy=retry_policy,
            concurrency=concurrency,
            timezone=timezone,
        )

    def pause(self) -> None:
        if self._status != ScheduleStatus.ACTIVE:
            from app.kernel.exceptions.errors import ConflictError

            raise ConflictError(message="Only active schedules can be paused")
        self._status = ScheduleStatus.PAUSED
        self.touch()
        self.increment_version()

    def resume(self) -> None:
        if self._status != ScheduleStatus.PAUSED:
            from app.kernel.exceptions.errors import ConflictError

            raise ConflictError(message="Only paused schedules can be resumed")
        self._status = ScheduleStatus.ACTIVE
        self.touch()
        self.increment_version()

    def record_run(self, success: bool) -> None:
        self._last_run_at = datetime.now(UTC)
        self._run_count += 1
        if not success:
            self._failure_count += 1
        self.touch()

    def update_next_run(self, next_run: datetime) -> None:
        self._next_run_at = next_run
        self.touch()


_CRON_PATTERN = re.compile(
    r"^(\*|([0-9]|[1-5][0-9])|(\*/[1-9][0-9]*)|([0-9]+-[0-9]+))\s+"
    r"(\*|([0-9]|1[0-9]|2[0-3])|(\*/[1-9][0-9]*)|([0-9]+-[0-9]+))\s+"
    r"(\*|([1-9]|[12][0-9]|3[01])|(\*/[1-9][0-9]*)|([0-9]+-[0-9]+))\s+"
    r"(\*|([1-9]|1[0-2])|(\*/[1-9][0-9]*)|([0-9]+-[0-9]+))\s+"
    r"(\*|([0-6])|(\*/[1-9][0-9]*)|([0-9]+-[0-9]+))"
    r"(\s+\S+)?$"
)


def validate_cron(expression: str) -> bool:
    """Validate a cron expression (5-6 fields)."""
    if not _CRON_PATTERN.match(expression.strip()):
        from app.kernel.exceptions.errors import ValidationError

        raise ValidationError(
            message=f"Invalid cron expression: {expression}",
            field="cron_expression",
        )
    return True
