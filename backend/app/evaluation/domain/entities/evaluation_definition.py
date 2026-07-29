"""Evaluation definition aggregate root.

Represents a saved evaluation configuration that can be executed
one or more times as EvaluationRuns. Manages its own lifecycle
(DRAFT -> READY -> ARCHIVED) and raises domain events on mutations.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.evaluation.domain.enums.evaluation_enums import EvaluationStatus
from app.evaluation.domain.events.evaluation_definition_events import (
    EvaluationDefinitionArchived,
    EvaluationDefinitionCreated,
    EvaluationDefinitionDeleted,
    EvaluationDefinitionDuplicated,
    EvaluationDefinitionUpdated,
)
from app.evaluation.domain.value_objects.evaluation_definition_vos import (
    EvaluationDescription,
    EvaluationName,
    MetricId,
    ProviderId,
)
from app.kernel.entities.base import AggregateRoot, UUIDv7, VersionMixin
from app.kernel.exceptions.errors import ConflictError, ValidationError


class Evaluation(AggregateRoot, VersionMixin):
    """Evaluation definition aggregate root.

    Encapsulates a saved evaluation configuration including its
    name, description, provider, model, metrics, tags, and full
    execution configuration. Enforces lifecycle invariants and
    raises domain events on every mutation.
    """

    def __init__(
        self,
        *,
        entity_id: UUIDv7 | None = None,
        project_id: str,
        dataset_id: str | None,
        name: EvaluationName,
        description: EvaluationDescription | None = None,
        provider: ProviderId,
        model: str,
        metrics: tuple[MetricId, ...],
        tags: tuple[str, ...] = (),
        configuration: dict[str, Any] | None = None,
        status: EvaluationStatus = EvaluationStatus.DRAFT,
        created_by: str | None = None,
    ) -> None:
        """Initialize an evaluation definition.

        Args:
            entity_id: Optional UUIDv7 identifier.
            project_id: The project this evaluation belongs to.
            dataset_id: Optional dataset identifier.
            name: Validated evaluation name.
            description: Optional validated description.
            provider: Validated provider identifier.
            model: Model identifier string.
            metrics: Tuple of validated metric identifiers.
            tags: Tuple of tag strings.
            configuration: Optional execution configuration as dict.
            status: Initial lifecycle status.
            created_by: Optional creator identifier.

        """
        super().__init__(entity_id=entity_id)
        VersionMixin.__init__(self)
        self._project_id = project_id
        self._dataset_id = dataset_id
        self._name = name
        self._description = description
        self._provider = provider
        self._model = model
        self._metrics = metrics
        self._tags = tags
        self._configuration = configuration or {}
        self._status = status
        self._created_by = created_by

    @property
    def project_id(self) -> str:
        """Return the project identifier."""
        return self._project_id

    @property
    def dataset_id(self) -> str | None:
        """Return the dataset identifier."""
        return self._dataset_id

    @property
    def name(self) -> EvaluationName:
        """Return the evaluation name."""
        return self._name

    @property
    def description(self) -> EvaluationDescription | None:
        """Return the evaluation description."""
        return self._description

    @property
    def provider(self) -> ProviderId:
        """Return the provider identifier."""
        return self._provider

    @property
    def model(self) -> str:
        """Return the model identifier."""
        return self._model

    @property
    def metrics(self) -> tuple[MetricId, ...]:
        """Return the metric identifiers."""
        return self._metrics

    @property
    def tags(self) -> tuple[str, ...]:
        """Return the tags."""
        return self._tags

    @property
    def configuration(self) -> Mapping[str, Any]:
        """Return the execution configuration as an immutable view."""
        return self._configuration

    @property
    def status(self) -> EvaluationStatus:
        """Return the lifecycle status."""
        return self._status

    @property
    def created_by(self) -> str | None:
        """Return the creator identifier."""
        return self._created_by

    def update(
        self,
        *,
        name: EvaluationName | None = None,
        description: EvaluationDescription | None = None,
        provider: ProviderId | None = None,
        model: str | None = None,
        metrics: tuple[MetricId, ...] | None = None,
        tags: tuple[str, ...] | None = None,
        configuration: dict[str, Any] | None = None,
        dataset_id: str | None = None,
    ) -> None:
        """Update evaluation definition fields.

        Only DRAFT evaluations can be updated.

        Args:
            name: New name, or None to keep current.
            description: New description, or None to keep current.
            provider: New provider, or None to keep current.
            model: New model, or None to keep current.
            metrics: New metrics, or None to keep current.
            tags: New tags, or None to keep current.
            configuration: New configuration, or None to keep current.
            dataset_id: New dataset_id, or None to keep current.

        Raises:
            ConflictError: If the evaluation is not in DRAFT status.

        """
        if self._status != EvaluationStatus.DRAFT:
            raise ConflictError(
                message="Only draft evaluations can be updated",
                details={"evaluation_id": str(self.id), "status": self._status.value},
            )
        if name is not None:
            self._name = name
        if description is not None:
            self._description = description
        if provider is not None:
            self._provider = provider
        if model is not None:
            self._model = model
        if metrics is not None:
            self._metrics = metrics
        if tags is not None:
            self._tags = tags
        if configuration is not None:
            self._configuration = configuration
        if dataset_id is not None:
            self._dataset_id = dataset_id
        self.touch()
        self.increment_version()
        self.raise_event(
            EvaluationDefinitionUpdated(
                evaluation_id=self.id,
                project_id=self._project_id,
                name=str(self._name.value),
                correlation_id=str(self.id),
            ),
        )

    def mark_ready(self) -> None:
        """Transition from DRAFT to READY.

        Raises:
            ConflictError: If not in DRAFT status.

        """
        if self._status != EvaluationStatus.DRAFT:
            raise ConflictError(
                message="Only draft evaluations can be marked ready",
                details={"evaluation_id": str(self.id), "status": self._status.value},
            )
        self._status = EvaluationStatus.READY
        self.touch()
        self.increment_version()

    def archive(self) -> None:
        """Archive this evaluation definition.

        Transitions from READY or DRAFT to ARCHIVED.

        Raises:
            ConflictError: If already archived.

        """
        if self._status == EvaluationStatus.ARCHIVED:
            raise ConflictError(
                message="Evaluation is already archived",
                details={"evaluation_id": str(self.id)},
            )
        self._status = EvaluationStatus.ARCHIVED
        self.touch()
        self.increment_version()
        self.raise_event(
            EvaluationDefinitionArchived(
                evaluation_id=self.id,
                project_id=self._project_id,
                correlation_id=str(self.id),
            ),
        )

    def delete(self) -> None:
        """Mark evaluation for deletion.

        Raises a domain event. The repository handles actual deletion.

        Raises:
            ConflictError: If already archived.

        """
        if self._status == EvaluationStatus.ARCHIVED:
            raise ConflictError(
                message="Archived evaluations cannot be deleted",
                details={"evaluation_id": str(self.id)},
            )
        self.raise_event(
            EvaluationDefinitionDeleted(
                evaluation_id=self.id,
                project_id=self._project_id,
                correlation_id=str(self.id),
            ),
        )

    def duplicate(self, new_name: EvaluationName) -> Evaluation:
        """Create a duplicate of this evaluation with a new name.

        Args:
            new_name: Name for the duplicated evaluation.

        Returns:
            A new Evaluation instance with DRAFT status.

        """
        duplicate = Evaluation(
            project_id=self._project_id,
            dataset_id=self._dataset_id,
            name=new_name,
            description=self._description,
            provider=self._provider,
            model=self._model,
            metrics=self._metrics,
            tags=self._tags,
            configuration=dict(self._configuration),
            status=EvaluationStatus.DRAFT,
            created_by=self._created_by,
        )
        duplicate.raise_event(
            EvaluationDefinitionDuplicated(
                source_id=self.id,
                new_id=duplicate.id,
                project_id=self._project_id,
                name=str(new_name.value),
                correlation_id=str(self.id),
            ),
        )
        return duplicate

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        dataset_id: str | None,
        name: EvaluationName,
        description: EvaluationDescription | None = None,
        provider: ProviderId,
        model: str,
        metrics: tuple[MetricId, ...],
        tags: tuple[str, ...] = (),
        configuration: dict[str, Any] | None = None,
        created_by: str | None = None,
    ) -> Evaluation:
        """Factory method to create a new evaluation definition.

        Validates invariants and raises EvaluationDefinitionCreated event.

        Args:
            project_id: The project identifier.
            dataset_id: Optional dataset identifier.
            name: Validated evaluation name.
            description: Optional description.
            provider: Validated provider identifier.
            model: Model identifier string.
            metrics: Tuple of metric identifiers.
            tags: Tuple of tag strings.
            configuration: Optional execution configuration.
            created_by: Optional creator identifier.

        Returns:
            A new Evaluation in DRAFT status.

        Raises:
            ValidationError: If required fields are missing.

        """
        if not metrics:
            raise ValidationError(
                message="At least one metric is required",
                field="metrics",
            )
        evaluation = cls(
            project_id=project_id,
            dataset_id=dataset_id,
            name=name,
            description=description,
            provider=provider,
            model=model,
            metrics=metrics,
            tags=tags,
            configuration=configuration,
            status=EvaluationStatus.DRAFT,
            created_by=created_by,
        )
        evaluation.raise_event(
            EvaluationDefinitionCreated(
                evaluation_id=evaluation.id,
                project_id=project_id,
                name=str(name.value),
                correlation_id=str(evaluation.id),
            ),
        )
        return evaluation
