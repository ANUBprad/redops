"""Tests for Red Team domain entities."""

from __future__ import annotations

import pytest

from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError, DomainError, ValidationError
from app.redteam.domain.entities import AttackDefinition, AttackRun
from app.redteam.domain.enums import (
    AttackCategory,
    AttackDefinitionStatus,
    AttackSeverity,
    AttackStatus,
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
)
from app.redteam.domain.value_objects import AttackConfiguration, AttackTemplate


class TestAttackDefinition:
    def test_create_success(self) -> None:
        definition = AttackDefinition.create(
            name="SQL Injection Test",
            description="Tests for prompt injection",
            category=AttackCategory.PROMPT_INJECTION,
            severity=AttackSeverity.HIGH,
        )
        assert definition.name == "SQL Injection Test"
        assert definition.description == "Tests for prompt injection"
        assert definition.category == AttackCategory.PROMPT_INJECTION
        assert definition.severity == AttackSeverity.HIGH
        assert definition.status == AttackDefinitionStatus.DRAFT
        assert definition.version == 1

    def test_create_raises_event(self) -> None:
        definition = AttackDefinition.create(name="test")
        events = definition.collect_events()
        assert any(isinstance(e, AttackDefinitionCreated) for e in events)

    def test_create_validates_name(self) -> None:
        with pytest.raises(ValidationError):
            AttackDefinition.create(name="")

    def test_update_success(self) -> None:
        definition = AttackDefinition.create(name="original", severity=AttackSeverity.LOW)
        definition.collect_events()
        definition.update(name="updated", severity=AttackSeverity.HIGH)
        assert definition.name == "updated"
        assert definition.severity == AttackSeverity.HIGH
        assert definition.version == 2

    def test_update_raises_event(self) -> None:
        definition = AttackDefinition.create(name="test")
        definition.collect_events()
        definition.update(name="new-name")
        events = definition.collect_events()
        assert any(isinstance(e, AttackDefinitionUpdated) for e in events)

    def test_update_rejects_empty_name(self) -> None:
        definition = AttackDefinition.create(name="test")
        with pytest.raises(ValidationError):
            definition.update(name="")

    def test_update_fails_when_archived(self) -> None:
        definition = AttackDefinition.create(name="test")
        definition.archive()
        with pytest.raises(ConflictError):
            definition.update(name="new")

    def test_activate_success(self) -> None:
        definition = AttackDefinition.create(name="test")
        definition.activate()
        assert definition.status == AttackDefinitionStatus.ACTIVE

    def test_activate_fails_when_not_draft(self) -> None:
        definition = AttackDefinition.create(name="test")
        definition.activate()
        with pytest.raises(ConflictError):
            definition.activate()

    def test_archive_success(self) -> None:
        definition = AttackDefinition.create(name="test")
        definition.archive()
        assert definition.status == AttackDefinitionStatus.ARCHIVED

    def test_archive_fails_when_already_archived(self) -> None:
        definition = AttackDefinition.create(name="test")
        definition.archive()
        with pytest.raises(ConflictError):
            definition.archive()

    def test_lifecycle_events(self) -> None:
        definition = AttackDefinition.create(name="test")
        definition.collect_events()
        definition.activate()
        events = definition.collect_events()
        assert any(isinstance(e, AttackDefinitionActivated) for e in events)
        definition.archive()
        events = definition.collect_events()
        assert any(isinstance(e, AttackDefinitionArchived) for e in events)


class TestAttackRun:
    def test_create_success(self) -> None:
        def_id = UUIDv7.generate()
        run = AttackRun.create(
            evaluation_run_id=UUIDv7.generate(),
            attack_definition_ids=(def_id,),
        )
        assert run.status == AttackStatus.CREATED
        assert run.evaluation_run_id is not None
        assert def_id in run.attack_definition_ids
        assert run.items_total == 0
        assert run.progress == 0.0

    def test_create_raises_event(self) -> None:
        run = AttackRun.create()
        events = run.collect_events()
        assert any(isinstance(e, AttackRunCreated) for e in events)

    def test_queue_success(self) -> None:
        run = AttackRun.create()
        run.queue()
        assert run.status == AttackStatus.QUEUED

    def test_queue_fails_when_not_created(self) -> None:
        run = AttackRun.create()
        run.queue()
        with pytest.raises(ConflictError):
            run.queue()

    def test_start_success(self) -> None:
        run = AttackRun.create()
        run.queue()
        run.start(total_items=10)
        assert run.status == AttackStatus.RUNNING
        assert run.items_total == 10
        assert run.started_at is not None

    def test_start_fails_when_not_queued(self) -> None:
        run = AttackRun.create()
        with pytest.raises(ConflictError):
            run.start(total_items=5)

    def test_complete_success(self) -> None:
        run = AttackRun.create()
        run.queue()
        run.start(total_items=3)
        run.complete()
        assert run.status == AttackStatus.COMPLETED
        assert run.completed_at is not None

    def test_complete_fails_when_not_running(self) -> None:
        run = AttackRun.create()
        with pytest.raises(ConflictError):
            run.complete()

    def test_fail_success(self) -> None:
        run = AttackRun.create()
        run.queue()
        run.start(total_items=5)
        run.fail(error_message="Provider error")
        assert run.status == AttackStatus.FAILED

    def test_fail_fails_from_terminal(self) -> None:
        run = AttackRun.create()
        run.queue()
        run.start(total_items=1)
        run.complete()
        with pytest.raises(ConflictError):
            run.fail()

    def test_cancel_success(self) -> None:
        run = AttackRun.create()
        run.queue()
        run.start(total_items=10)
        run.cancel()
        assert run.status == AttackStatus.CANCELLED

    def test_cancel_fails_from_terminal(self) -> None:
        run = AttackRun.create()
        run.queue()
        run.start(total_items=1)
        run.complete()
        with pytest.raises(ConflictError):
            run.cancel()

    def test_record_scenario_result_passed(self) -> None:
        run = AttackRun.create()
        run.queue()
        run.start(total_items=5)
        run.record_scenario_result(is_violation=False, is_error=False)
        assert run.items_completed == 1
        assert run.items_passed == 1
        assert run.items_failed == 0
        assert run.items_violated == 0

    def test_record_scenario_result_violated(self) -> None:
        run = AttackRun.create()
        run.queue()
        run.start(total_items=5)
        run.record_scenario_result(is_violation=True, is_error=False)
        assert run.items_completed == 1
        assert run.items_violated == 1

    def test_record_scenario_result_failed(self) -> None:
        run = AttackRun.create()
        run.queue()
        run.start(total_items=5)
        run.record_scenario_result(is_violation=False, is_error=True)
        assert run.items_completed == 1
        assert run.items_failed == 1

    def test_record_scenario_result_fails_when_not_running(self) -> None:
        run = AttackRun.create()
        with pytest.raises(DomainError):
            run.record_scenario_result(is_violation=False, is_error=False)

    def test_progress_calculation(self) -> None:
        run = AttackRun.create()
        assert run.progress == 0.0
        run.queue()
        run.start(total_items=10)
        run.record_scenario_result(is_violation=False, is_error=False)
        assert run.progress == 0.1
        for _ in range(9):
            run.record_scenario_result(is_violation=False, is_error=False)
        assert run.progress == 1.0

    def test_lifecycle_events(self) -> None:
        run = AttackRun.create()
        run.collect_events()
        run.queue()
        events = run.collect_events()
        assert any(isinstance(e, AttackRunQueued) for e in events)
        run.start(total_items=5)
        events = run.collect_events()
        assert any(isinstance(e, AttackRunStarted) for e in events)
        run.complete()
        events = run.collect_events()
        assert any(isinstance(e, AttackRunCompleted) for e in events)
