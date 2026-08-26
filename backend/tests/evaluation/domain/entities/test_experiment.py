"""Tests for the Experiment aggregate."""

from __future__ import annotations

import pytest

from app.evaluation.domain.entities.experiment import Experiment
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
from app.kernel.exceptions.errors import ConflictError


def _make_experiment(
    *,
    name: str = "test-experiment",
    project_id: str = "proj-1",
) -> Experiment:
    """Create a minimal Experiment for testing."""
    return Experiment.create(
        project_id=project_id,
        name=ExperimentName(value=name),
    )


class TestExperimentCreate:
    """Tests for Experiment.create factory method."""

    def test_create_raises_event(self) -> None:
        experiment = _make_experiment()
        events = experiment.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], ExperimentCreated)

    def test_create_sets_draft_status(self) -> None:
        experiment = _make_experiment()
        assert experiment.status == ExperimentStatus.DRAFT

    def test_create_with_all_fields(self) -> None:
        experiment = Experiment.create(
            project_id="proj-1",
            name=ExperimentName(value="full-experiment"),
            description=ExperimentDescription(value="A full experiment"),
            hypothesis="Claude is better than GPT-4",
            tags=("safety", "production"),
            created_by="user-1",
        )
        assert str(experiment.name.value) == "full-experiment"
        assert experiment.description is not None
        assert experiment.hypothesis == "Claude is better than GPT-4"
        assert experiment.tags == ("safety", "production")
        assert experiment.created_by == "user-1"

    def test_create_requires_name(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            Experiment.create(
                project_id="proj-1",
                name=ExperimentName(value=""),
            )


class TestExperimentLifecycle:
    """Tests for Experiment lifecycle transitions."""

    def test_activate_from_draft(self) -> None:
        experiment = _make_experiment()
        experiment.activate()
        assert experiment.status == ExperimentStatus.ACTIVE

    def test_activate_non_draft_raises(self) -> None:
        experiment = _make_experiment()
        experiment.activate()
        with pytest.raises(ConflictError, match="Only draft"):
            experiment.activate()

    def test_complete_from_active(self) -> None:
        experiment = _make_experiment()
        experiment.activate()
        experiment.complete()
        assert experiment.status == ExperimentStatus.COMPLETED
        events = experiment.collect_events()
        assert any(isinstance(e, ExperimentCompleted) for e in events)

    def test_complete_non_active_raises(self) -> None:
        experiment = _make_experiment()
        with pytest.raises(ConflictError, match="Only active"):
            experiment.complete()

    def test_archive_from_any_status(self) -> None:
        experiment = _make_experiment()
        experiment.archive()
        assert experiment.status == ExperimentStatus.ARCHIVED

    def test_archive_already_archived_raises(self) -> None:
        experiment = _make_experiment()
        experiment.archive()
        with pytest.raises(ConflictError, match="already archived"):
            experiment.archive()

    def test_update_draft(self) -> None:
        experiment = _make_experiment()
        experiment.update(name=ExperimentName(value="new-name"))
        assert str(experiment.name.value) == "new-name"

    def test_update_completed_raises(self) -> None:
        experiment = _make_experiment()
        experiment.activate()
        experiment.complete()
        with pytest.raises(ConflictError, match="Completed or archived"):
            experiment.update(name=ExperimentName(value="new-name"))

    def test_set_baseline(self) -> None:
        experiment = _make_experiment()
        experiment.set_baseline("run-123")
        assert experiment.baseline_run_id == "run-123"
        events = experiment.collect_events()
        assert any(isinstance(e, ExperimentBaselineSet) for e in events)

    def test_update_raises_event(self) -> None:
        experiment = _make_experiment()
        experiment.update(conclusion="GPT-4 is better")
        events = experiment.collect_events()
        assert any(isinstance(e, ExperimentUpdated) for e in events)
