"""Experiment aggregate root.

Groups related evaluation runs under a hypothesis for comparative
analysis. Manages its own lifecycle (DRAFT -> ACTIVE -> COMPLETED -> ARCHIVED)
and raises domain events on mutations.
"""

from __future__ import annotations

from app.evaluation.domain.enums.experiment_enums import ExperimentStatus
from app.evaluation.domain.events.experiment_events import (
    ExperimentArchived,
    ExperimentBaselineSet,
    ExperimentCompleted,
    ExperimentCreated,
    ExperimentUpdated,
)
from app.evaluation.domain.value_objects.experiment_value_objects import (
    ExperimentDescription,
    ExperimentName,
)
from app.kernel.entities.base import AggregateRoot, UUIDv7, VersionMixin
from app.kernel.exceptions.errors import ConflictError


class Experiment(AggregateRoot, VersionMixin):
    """Experiment aggregate root.

    An experiment groups evaluation runs that test a hypothesis.
    Users compare runs within an experiment and record conclusions.
    """

    def __init__(
        self,
        *,
        entity_id: UUIDv7 | None = None,
        project_id: str,
        name: ExperimentName,
        description: ExperimentDescription | None = None,
        hypothesis: str | None = None,
        status: ExperimentStatus = ExperimentStatus.DRAFT,
        baseline_run_id: str | None = None,
        conclusion: str | None = None,
        tags: tuple[str, ...] = (),
        created_by: str | None = None,
    ) -> None:
        """Initialize an experiment.

        Args:
            entity_id: Optional UUIDv7 identifier.
            project_id: The project this experiment belongs to.
            name: Validated experiment name.
            description: Optional validated description.
            hypothesis: Optional hypothesis text.
            status: Initial lifecycle status.
            baseline_run_id: Optional baseline run ID for comparison.
            conclusion: Optional recorded conclusion.
            tags: Tuple of tag strings.
            created_by: Optional creator identifier.

        """
        super().__init__(entity_id=entity_id)
        VersionMixin.__init__(self)
        self._project_id = project_id
        self._name = name
        self._description = description
        self._hypothesis = hypothesis
        self._status = status
        self._baseline_run_id = baseline_run_id
        self._conclusion = conclusion
        self._tags = tags
        self._created_by = created_by

    @property
    def project_id(self) -> str:
        """Return the project identifier."""
        return self._project_id

    @property
    def name(self) -> ExperimentName:
        """Return the experiment name."""
        return self._name

    @property
    def description(self) -> ExperimentDescription | None:
        """Return the experiment description."""
        return self._description

    @property
    def hypothesis(self) -> str | None:
        """Return the hypothesis text."""
        return self._hypothesis

    @property
    def status(self) -> ExperimentStatus:
        """Return the lifecycle status."""
        return self._status

    @property
    def baseline_run_id(self) -> str | None:
        """Return the baseline run ID."""
        return self._baseline_run_id

    @property
    def conclusion(self) -> str | None:
        """Return the recorded conclusion."""
        return self._conclusion

    @property
    def tags(self) -> tuple[str, ...]:
        """Return the tags."""
        return self._tags

    @property
    def created_by(self) -> str | None:
        """Return the creator identifier."""
        return self._created_by

    def update(
        self,
        *,
        name: ExperimentName | None = None,
        description: ExperimentDescription | None = None,
        hypothesis: str | None = None,
        conclusion: str | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> None:
        """Update experiment metadata.

        Only DRAFT and ACTIVE experiments can be updated.

        Args:
            name: New name, or None to keep current.
            description: New description, or None to keep current.
            hypothesis: New hypothesis, or None to keep current.
            conclusion: New conclusion, or None to keep current.
            tags: New tags, or None to keep current.

        Raises:
            ConflictError: If the experiment is COMPLETED or ARCHIVED.

        """
        if self._status in (ExperimentStatus.COMPLETED, ExperimentStatus.ARCHIVED):
            raise ConflictError(
                message="Completed or archived experiments cannot be updated",
                details={"experiment_id": str(self.id), "status": self._status.value},
            )
        if name is not None:
            self._name = name
        if description is not None:
            self._description = description
        if hypothesis is not None:
            self._hypothesis = hypothesis
        if conclusion is not None:
            self._conclusion = conclusion
        if tags is not None:
            self._tags = tags
        self.touch()
        self.increment_version()
        self.raise_event(
            ExperimentUpdated(
                experiment_id=self.id,
                project_id=self._project_id,
                name=str(self._name.value),
                correlation_id=str(self.id),
            ),
        )

    def activate(self) -> None:
        """Transition from DRAFT to ACTIVE.

        Raises:
            ConflictError: If not in DRAFT status.

        """
        if self._status != ExperimentStatus.DRAFT:
            raise ConflictError(
                message="Only draft experiments can be activated",
                details={"experiment_id": str(self.id), "status": self._status.value},
            )
        self._status = ExperimentStatus.ACTIVE
        self.touch()
        self.increment_version()

    def complete(self) -> None:
        """Transition from ACTIVE to COMPLETED.

        Raises:
            ConflictError: If not in ACTIVE status.

        """
        if self._status != ExperimentStatus.ACTIVE:
            raise ConflictError(
                message="Only active experiments can be completed",
                details={"experiment_id": str(self.id), "status": self._status.value},
            )
        self._status = ExperimentStatus.COMPLETED
        self.touch()
        self.increment_version()
        self.raise_event(
            ExperimentCompleted(
                experiment_id=self.id,
                project_id=self._project_id,
                correlation_id=str(self.id),
            ),
        )

    def archive(self) -> None:
        """Archive the experiment.

        Transitions from any non-ARCHIVED status to ARCHIVED.

        Raises:
            ConflictError: If already archived.

        """
        if self._status == ExperimentStatus.ARCHIVED:
            raise ConflictError(
                message="Experiment is already archived",
                details={"experiment_id": str(self.id)},
            )
        self._status = ExperimentStatus.ARCHIVED
        self.touch()
        self.increment_version()
        self.raise_event(
            ExperimentArchived(
                experiment_id=self.id,
                project_id=self._project_id,
                correlation_id=str(self.id),
            ),
        )

    def set_baseline(self, run_id: str) -> None:
        """Set the baseline run for comparison.

        Args:
            run_id: The evaluation run ID to use as baseline.

        """
        self._baseline_run_id = run_id
        self.touch()
        self.increment_version()
        self.raise_event(
            ExperimentBaselineSet(
                experiment_id=self.id,
                project_id=self._project_id,
                baseline_run_id=run_id,
                correlation_id=str(self.id),
            ),
        )

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        name: ExperimentName,
        description: ExperimentDescription | None = None,
        hypothesis: str | None = None,
        tags: tuple[str, ...] = (),
        created_by: str | None = None,
    ) -> Experiment:
        """Factory method to create a new experiment.

        Args:
            project_id: The project identifier.
            name: Validated experiment name.
            description: Optional description.
            hypothesis: Optional hypothesis text.
            tags: Tuple of tag strings.
            created_by: Optional creator identifier.

        Returns:
            A new Experiment in DRAFT status.

        """
        experiment = cls(
            project_id=project_id,
            name=name,
            description=description,
            hypothesis=hypothesis,
            status=ExperimentStatus.DRAFT,
            tags=tags,
            created_by=created_by,
        )
        experiment.raise_event(
            ExperimentCreated(
                experiment_id=experiment.id,
                project_id=project_id,
                name=str(name.value),
                correlation_id=str(experiment.id),
            ),
        )
        return experiment
