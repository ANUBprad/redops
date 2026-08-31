"""Aggregate roots for the Red Team domain."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.kernel.entities.base import AggregateRoot, UUIDv7, VersionMixin
from app.kernel.exceptions.errors import ConflictError, DomainError, ValidationError
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


class AttackDefinition(AggregateRoot, VersionMixin):
    """An attack definition - the blueprint for a type of LLM attack."""

    def __init__(
        self,
        *,
        entity_id: UUIDv7 | None = None,
        name: str = "",
        description: str = "",
        category: AttackCategory = AttackCategory.PROMPT_INJECTION,
        severity: AttackSeverity = AttackSeverity.MEDIUM,
        template: AttackTemplate | None = None,
        parameters: dict[str, Any] | None = None,
        tags: tuple[str, ...] | None = None,
        status: AttackDefinitionStatus = AttackDefinitionStatus.DRAFT,
        created_by: str | None = None,
    ) -> None:
        super().__init__(entity_id=entity_id)
        VersionMixin.__init__(self)
        self._name = name
        self._description = description
        self._category = category
        self._severity = severity
        self._template = template or AttackTemplate(name=name)
        self._parameters = parameters or {}
        self._tags = tags or ()
        self._status = status
        self._created_by = created_by

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def category(self) -> AttackCategory:
        return self._category

    @property
    def severity(self) -> AttackSeverity:
        return self._severity

    @property
    def template(self) -> AttackTemplate:
        return self._template

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    @property
    def tags(self) -> tuple[str, ...]:
        return self._tags

    @property
    def status(self) -> AttackDefinitionStatus:
        return self._status

    @property
    def created_by(self) -> str | None:
        return self._created_by

    @classmethod
    def create(
        cls,
        *,
        name: str,
        description: str = "",
        category: AttackCategory = AttackCategory.PROMPT_INJECTION,
        severity: AttackSeverity = AttackSeverity.MEDIUM,
        template: AttackTemplate | None = None,
        parameters: dict[str, Any] | None = None,
        tags: tuple[str, ...] | None = None,
        created_by: str | None = None,
    ) -> AttackDefinition:
        if not name or not name.strip():
            raise ValidationError(message="Attack definition name is required", field="name")

        definition = cls(
            name=name.strip(),
            description=description.strip(),
            category=category,
            severity=severity,
            template=template,
            parameters=parameters or {},
            tags=tags or (),
            created_by=created_by,
        )
        definition.raise_event(
            AttackDefinitionCreated(
                definition_id=definition.id,
                name=definition.name,
                category=definition.category.value,
                severity=definition.severity.value,
            ),
        )
        return definition

    def update(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        category: AttackCategory | None = None,
        severity: AttackSeverity | None = None,
        template: AttackTemplate | None = None,
        parameters: dict[str, Any] | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> None:
        if not self._status.is_editable:
            raise ConflictError(
                message=f"Cannot update definition in {self._status.value} state",
                details={"definition_id": str(self.id), "status": self._status.value},
            )

        if name is not None:
            if not name.strip():
                raise ValidationError(message="Name cannot be empty", field="name")
            self._name = name.strip()
        if description is not None:
            self._description = description.strip()
        if category is not None:
            self._category = category
        if severity is not None:
            self._severity = severity
        if template is not None:
            self._template = template
        if parameters is not None:
            self._parameters = parameters
        if tags is not None:
            self._tags = tags

        self.increment_version()
        self.raise_event(
            AttackDefinitionUpdated(
                definition_id=self.id,
                name=self.name,
            ),
        )

    def activate(self) -> None:
        if self._status != AttackDefinitionStatus.DRAFT:
            raise ConflictError(
                message=f"Cannot activate definition in {self._status.value} state",
                details={"definition_id": str(self.id), "status": self._status.value},
            )
        self._status = AttackDefinitionStatus.ACTIVE
        self.increment_version()
        self.raise_event(
            AttackDefinitionActivated(
                definition_id=self.id,
                name=self.name,
            ),
        )

    def archive(self) -> None:
        if self._status == AttackDefinitionStatus.ARCHIVED:
            raise ConflictError(
                message="Definition is already archived",
                details={"definition_id": str(self.id)},
            )
        self._status = AttackDefinitionStatus.ARCHIVED
        self.increment_version()
        self.raise_event(
            AttackDefinitionArchived(
                definition_id=self.id,
                name=self.name,
            ),
        )


class AttackRun(AggregateRoot, VersionMixin):
    """An execution of one or more attacks against a target model."""

    def __init__(
        self,
        *,
        entity_id: UUIDv7 | None = None,
        evaluation_run_id: UUIDv7 | None = None,
        attack_definition_ids: tuple[UUIDv7, ...] = (),
        configuration: AttackConfiguration | None = None,
        status: AttackStatus = AttackStatus.CREATED,
        items_total: int = 0,
        items_completed: int = 0,
        items_passed: int = 0,
        items_violated: int = 0,
        items_failed: int = 0,
        campaign_results: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(entity_id=entity_id)
        VersionMixin.__init__(self)
        self._evaluation_run_id = evaluation_run_id
        self._attack_definition_ids = attack_definition_ids
        self._configuration = configuration or AttackConfiguration()
        self._status = status
        self._items_total = items_total
        self._items_completed = items_completed
        self._items_passed = items_passed
        self._items_violated = items_violated
        self._items_failed = items_failed
        self._campaign_results = campaign_results
        self._started_at: datetime | None = None
        self._completed_at: datetime | None = None

    @property
    def evaluation_run_id(self) -> UUIDv7 | None:
        return self._evaluation_run_id

    @property
    def attack_definition_ids(self) -> tuple[UUIDv7, ...]:
        return self._attack_definition_ids

    @property
    def configuration(self) -> AttackConfiguration:
        return self._configuration

    @property
    def status(self) -> AttackStatus:
        return self._status

    @property
    def items_total(self) -> int:
        return self._items_total

    @property
    def items_completed(self) -> int:
        return self._items_completed

    @property
    def items_passed(self) -> int:
        return self._items_passed

    @property
    def items_violated(self) -> int:
        return self._items_violated

    @property
    def items_failed(self) -> int:
        return self._items_failed

    @property
    def campaign_results(self) -> dict[str, Any] | None:
        return self._campaign_results

    @property
    def started_at(self) -> datetime | None:
        return self._started_at

    @property
    def completed_at(self) -> datetime | None:
        return self._completed_at

    @property
    def progress(self) -> float:
        if self._items_total == 0:
            return 0.0
        return self._items_completed / self._items_total

    @classmethod
    def create(
        cls,
        *,
        evaluation_run_id: UUIDv7 | None = None,
        attack_definition_ids: tuple[UUIDv7, ...] = (),
        configuration: AttackConfiguration | None = None,
    ) -> AttackRun:
        run = cls(
            evaluation_run_id=evaluation_run_id,
            attack_definition_ids=attack_definition_ids,
            configuration=configuration,
        )
        run.raise_event(
            AttackRunCreated(
                run_id=run.id,
                evaluation_run_id=evaluation_run_id,
                attack_count=len(attack_definition_ids),
            ),
        )
        return run

    def queue(self) -> None:
        if self._status != AttackStatus.CREATED:
            raise ConflictError(
                message=f"Cannot queue run in {self._status.value} state",
                details={"run_id": str(self.id), "status": self._status.value},
            )
        self._status = AttackStatus.QUEUED
        self.raise_event(
            AttackRunQueued(run_id=self.id),
        )

    def start(self, total_items: int) -> None:
        if self._status != AttackStatus.QUEUED:
            raise ConflictError(
                message=f"Cannot start run in {self._status.value} state",
                details={"run_id": str(self.id), "status": self._status.value},
            )
        self._status = AttackStatus.RUNNING
        self._items_total = total_items
        self._started_at = datetime.now(UTC)
        self.raise_event(
            AttackRunStarted(
                run_id=self.id,
                items_total=total_items,
            ),
        )

    def complete(self) -> None:
        if self._status != AttackStatus.RUNNING:
            raise ConflictError(
                message=f"Cannot complete run in {self._status.value} state",
                details={"run_id": str(self.id), "status": self._status.value},
            )
        self._status = AttackStatus.COMPLETED
        self._completed_at = datetime.now(UTC)
        self.raise_event(
            AttackRunCompleted(
                run_id=self.id,
                items_total=self._items_total,
                items_completed=self._items_completed,
                items_passed=self._items_passed,
                items_violated=self._items_violated,
            ),
        )

    def fail(self, error_message: str = "") -> None:
        if self._status.is_terminal:
            raise ConflictError(
                message=f"Cannot fail run in {self._status.value} state",
                details={"run_id": str(self.id), "status": self._status.value},
            )
        self._status = AttackStatus.FAILED
        self._completed_at = datetime.now(UTC)
        self.raise_event(
            AttackRunFailed(
                run_id=self.id,
                error_message=error_message,
            ),
        )

    def cancel(self) -> None:
        if self._status.is_terminal:
            raise ConflictError(
                message=f"Cannot cancel run in {self._status.value} state",
                details={"run_id": str(self.id), "status": self._status.value},
            )
        self._status = AttackStatus.CANCELLED
        self._completed_at = datetime.now(UTC)
        self.raise_event(
            AttackRunCancelled(
                run_id=self.id,
                items_completed=self._items_completed,
            ),
        )

    def record_scenario_result(
        self,
        *,
        is_violation: bool,
        is_error: bool,
    ) -> None:
        if self._status != AttackStatus.RUNNING:
            raise DomainError(
                message=f"Cannot record result in {self._status.value} state",
            )
        self._items_completed += 1
        if is_error:
            self._items_failed += 1
        elif is_violation:
            self._items_violated += 1
        else:
            self._items_passed += 1

    def record_campaign_results(self, campaign_results: dict[str, Any]) -> None:
        """Attach the terminal campaign results to the run.

        Separately persisted (via ``persist_campaign_results``) so the
        full per-round prompts/responses/effectiveness/semantic data is
        durable and retrievable through the repository.
        """
        self._campaign_results = campaign_results
