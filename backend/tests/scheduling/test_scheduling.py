"""Tests for scheduling domain and services."""

from unittest.mock import AsyncMock

import pytest

from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError, NotFoundError, ValidationError
from app.scheduling.domain import (
    RetryPolicy,
    RetryStrategy,
    Schedule,
    ScheduleStatus,
    validate_cron,
)


def test_retry_policy_fixed() -> None:
    rp = RetryPolicy(max_retries=3, strategy=RetryStrategy.FIXED, base_delay_seconds=60)
    assert rp.delay_for_attempt(1) == 60
    assert rp.delay_for_attempt(2) == 60
    assert rp.delay_for_attempt(3) == 60


def test_retry_policy_exponential() -> None:
    rp = RetryPolicy(max_retries=5, strategy=RetryStrategy.EXPONENTIAL, base_delay_seconds=10)
    assert rp.delay_for_attempt(1) == 10
    assert rp.delay_for_attempt(2) == 20
    assert rp.delay_for_attempt(3) == 40
    assert rp.delay_for_attempt(4) == 80


def test_retry_policy_linear() -> None:
    rp = RetryPolicy(max_retries=5, strategy=RetryStrategy.LINEAR, base_delay_seconds=10)
    assert rp.delay_for_attempt(1) == 10
    assert rp.delay_for_attempt(2) == 20
    assert rp.delay_for_attempt(3) == 30


def test_retry_policy_max_delay_cap() -> None:
    rp = RetryPolicy(
        max_retries=10,
        strategy=RetryStrategy.EXPONENTIAL,
        base_delay_seconds=100,
        max_delay_seconds=500,
    )
    assert rp.delay_for_attempt(1) == 100
    assert rp.delay_for_attempt(10) == 500


def test_validate_cron_valid() -> None:
    assert validate_cron("0 0 * * *") is True
    assert validate_cron("*/5 * * * *") is True
    assert validate_cron("30 2 * * 1") is True
    assert validate_cron("0 */2 * * *") is True


def test_validate_cron_invalid() -> None:
    with pytest.raises(ValidationError):
        validate_cron("invalid")
    with pytest.raises(ValidationError):
        validate_cron("60 * * * *")


def test_schedule_creation() -> None:
    s = Schedule.create(
        name="Daily Eval",
        schedule_type="evaluation",
        cron_expression="0 0 * * *",
        created_by="user-1",
    )
    assert s.name == "Daily Eval"
    assert s.status == ScheduleStatus.ACTIVE
    assert s.run_count == 0


def test_schedule_pause_resume() -> None:
    s = Schedule.create(
        name="Test",
        schedule_type="evaluation",
        cron_expression="0 * * * *",
    )
    s.pause()
    assert s.status == ScheduleStatus.PAUSED
    s.resume()
    assert s.status == ScheduleStatus.ACTIVE


def test_schedule_pause_non_active_raises() -> None:
    s = Schedule.create(
        name="Test",
        schedule_type="evaluation",
        cron_expression="0 * * * *",
    )
    s.pause()
    with pytest.raises(ConflictError):
        s.pause()


def test_schedule_resume_non_paused_raises() -> None:
    s = Schedule.create(
        name="Test",
        schedule_type="evaluation",
        cron_expression="0 * * * *",
    )
    with pytest.raises(ConflictError):
        s.resume()


def test_schedule_record_run() -> None:
    s = Schedule.create(
        name="Test",
        schedule_type="evaluation",
        cron_expression="0 * * * *",
    )
    s.record_run(success=True)
    assert s.run_count == 1
    assert s.failure_count == 0
    assert s.last_run_at is not None


def test_schedule_record_failure() -> None:
    s = Schedule.create(
        name="Test",
        schedule_type="evaluation",
        cron_expression="0 * * * *",
    )
    s.record_run(success=False)
    assert s.run_count == 1
    assert s.failure_count == 1


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_id.return_value = None
    return repo


@pytest.mark.asyncio
async def test_create_schedule(mock_repo: AsyncMock) -> None:
    from app.scheduling.services import ScheduleService

    service = ScheduleService(mock_repo)
    schedule = await service.create_schedule(
        name="Test",
        schedule_type="evaluation",
        cron_expression="0 * * * *",
    )
    assert schedule.name == "Test"
    mock_repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_schedule_not_found(mock_repo: AsyncMock) -> None:
    from app.scheduling.services import ScheduleService

    service = ScheduleService(mock_repo)
    with pytest.raises(NotFoundError):
        await service.get_schedule(str(UUIDv7.generate()))
