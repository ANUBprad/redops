"""Tests for Scheduling domain entities."""

from app.scheduling.domain import (
    ConcurrencyConfig,
    RetryPolicy,
    RetryStrategy,
    Schedule,
    ScheduleStatus,
    ScheduleType,
    validate_cron,
)
from app.kernel.exceptions.errors import ValidationError

import pytest


def test_retry_policy_delay_exponential() -> None:
    policy = RetryPolicy(
        max_retries=5,
        strategy=RetryStrategy.EXPONENTIAL,
        base_delay_seconds=60,
        max_delay_seconds=3600,
    )
    assert policy.delay_for_attempt(1) == 60
    assert policy.delay_for_attempt(2) == 120
    assert policy.delay_for_attempt(3) == 240
    assert policy.delay_for_attempt(4) == 480
    assert policy.delay_for_attempt(5) == 960


def test_retry_policy_delay_fixed() -> None:
    policy = RetryPolicy(
        strategy=RetryStrategy.FIXED,
        base_delay_seconds=30,
    )
    assert policy.delay_for_attempt(1) == 30
    assert policy.delay_for_attempt(5) == 30


def test_retry_policy_delay_linear() -> None:
    policy = RetryPolicy(
        strategy=RetryStrategy.LINEAR,
        base_delay_seconds=10,
    )
    assert policy.delay_for_attempt(1) == 10
    assert policy.delay_for_attempt(3) == 30


def test_retry_policy_max_delay_cap() -> None:
    policy = RetryPolicy(
        strategy=RetryStrategy.EXPONENTIAL,
        base_delay_seconds=60,
        max_delay_seconds=300,
    )
    assert policy.delay_for_attempt(10) == 300


def test_validate_cron_valid() -> None:
    assert validate_cron("0 * * * *") is True
    assert validate_cron("*/5 * * * *") is True
    assert validate_cron("0 9 * * 1-5") is True


def test_validate_cron_invalid() -> None:
    with pytest.raises(ValidationError):
        validate_cron("invalid")
    with pytest.raises(ValidationError):
        validate_cron("* * *")


def test_schedule_create() -> None:
    schedule = Schedule.create(
        name="Daily Eval",
        schedule_type=ScheduleType.EVALUATION.value,
        cron_expression="0 9 * * *",
        task_config={"evaluation_id": "eval-1"},
        organization_id="org-1",
        project_id="proj-1",
        created_by="user-1",
    )
    assert schedule.name == "Daily Eval"
    assert schedule.schedule_type == ScheduleType.EVALUATION
    assert schedule.status == ScheduleStatus.ACTIVE


def test_schedule_pause_resume() -> None:
    schedule = Schedule.create(
        name="Test",
        schedule_type=ScheduleType.BENCHMARK.value,
        cron_expression="0 * * * *",
    )
    schedule.pause()
    assert schedule.status == ScheduleStatus.PAUSED
    schedule.resume()
    assert schedule.status == ScheduleStatus.ACTIVE


def test_schedule_record_run() -> None:
    schedule = Schedule.create(
        name="Test",
        schedule_type=ScheduleType.EVALUATION.value,
        cron_expression="0 * * * *",
    )
    schedule.record_run(success=True)
    assert schedule.run_count == 1
    assert schedule.failure_count == 0
    schedule.record_run(success=False)
    assert schedule.run_count == 2
    assert schedule.failure_count == 1
