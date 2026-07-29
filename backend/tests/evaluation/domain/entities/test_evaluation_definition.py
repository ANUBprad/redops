"""Tests for the Evaluation definition aggregate."""

from __future__ import annotations

import pytest

from app.evaluation.domain.entities.evaluation_definition import Evaluation
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
from app.kernel.exceptions.errors import ConflictError, ValidationError


def _make_evaluation(
    *,
    name: str = "test-eval",
    project_id: str = "proj-1",
    status: EvaluationStatus = EvaluationStatus.DRAFT,
) -> Evaluation:
    """Create a minimal Evaluation for testing."""
    return Evaluation.create(
        project_id=project_id,
        dataset_id="ds-1",
        name=EvaluationName(value=name),
        provider=ProviderId(value="openai"),
        model="gpt-4",
        metrics=(MetricId(value="accuracy"),),
    )


class TestEvaluationCreate:
    """Tests for Evaluation.create factory method."""

    def test_create_raises_event(self) -> None:
        """Factory method raises EvaluationDefinitionCreated event."""
        evaluation = _make_evaluation()
        events = evaluation.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], EvaluationDefinitionCreated)

    def test_create_sets_draft_status(self) -> None:
        """New evaluation starts in DRAFT status."""
        evaluation = _make_evaluation()
        assert evaluation.status == EvaluationStatus.DRAFT

    def test_create_requires_metrics(self) -> None:
        """Factory method raises ValidationError when no metrics provided."""
        with pytest.raises(ValidationError, match="At least one metric"):
            Evaluation.create(
                project_id="proj-1",
                dataset_id=None,
                name=EvaluationName(value="test"),
                provider=ProviderId(value="openai"),
                model="gpt-4",
                metrics=(),
            )

    def test_create_with_all_fields(self) -> None:
        """Factory method accepts all optional fields."""
        evaluation = Evaluation.create(
            project_id="proj-1",
            dataset_id="ds-1",
            name=EvaluationName(value="full-eval"),
            description=EvaluationDescription(value="A full evaluation"),
            provider=ProviderId(value="anthropic"),
            model="claude-3",
            metrics=(MetricId(value="f1"), MetricId(value="recall")),
            tags=("safety", "production"),
            configuration={"temperature": 0.5},
            created_by="user-1",
        )
        assert evaluation.project_id == "proj-1"
        assert evaluation.dataset_id == "ds-1"
        assert str(evaluation.name.value) == "full-eval"
        assert evaluation.description is not None
        assert evaluation.provider.value == "anthropic"
        assert evaluation.model == "claude-3"
        assert len(evaluation.metrics) == 2
        assert evaluation.tags == ("safety", "production")
        assert evaluation.configuration == {"temperature": 0.5}
        assert evaluation.created_by == "user-1"


class TestEvaluationUpdate:
    """Tests for Evaluation.update method."""

    def test_update_fields(self) -> None:
        """Update modifies specified fields."""
        evaluation = _make_evaluation()
        evaluation.update(
            name=EvaluationName(value="updated-name"),
            model="gpt-4-turbo",
            tags=("new-tag",),
        )
        assert str(evaluation.name.value) == "updated-name"
        assert evaluation.model == "gpt-4-turbo"
        assert evaluation.tags == ("new-tag",)

    def test_update_raises_event(self) -> None:
        """Update raises EvaluationDefinitionUpdated event."""
        evaluation = _make_evaluation()
        evaluation.collect_events()  # clear create event
        evaluation.update(name=EvaluationName(value="updated"))
        events = evaluation.collect_events()
        assert any(isinstance(e, EvaluationDefinitionUpdated) for e in events)

    def test_update_increments_version(self) -> None:
        """Update increments the version number."""
        evaluation = _make_evaluation()
        initial_version = evaluation.version
        evaluation.update(name=EvaluationName(value="updated"))
        assert evaluation.version == initial_version + 1

    def test_update_non_draft_raises(self) -> None:
        """Update raises ConflictError when not in DRAFT status."""
        evaluation = _make_evaluation()
        evaluation.mark_ready()
        with pytest.raises(ConflictError, match="Only draft"):
            evaluation.update(name=EvaluationName(value="fail"))


class TestEvaluationMarkReady:
    """Tests for Evaluation.mark_ready method."""

    def test_draft_to_ready(self) -> None:
        """DRAFT transitions to READY."""
        evaluation = _make_evaluation()
        evaluation.mark_ready()
        assert evaluation.status == EvaluationStatus.READY

    def test_non_draft_raises(self) -> None:
        """Non-DRAFT evaluation raises ConflictError."""
        evaluation = _make_evaluation()
        evaluation.mark_ready()
        with pytest.raises(ConflictError, match="Only draft"):
            evaluation.mark_ready()


class TestEvaluationArchive:
    """Tests for Evaluation.archive method."""

    def test_ready_to_archived(self) -> None:
        """READY transitions to ARCHIVED."""
        evaluation = _make_evaluation()
        evaluation.mark_ready()
        evaluation.archive()
        assert evaluation.status == EvaluationStatus.ARCHIVED

    def test_draft_to_archived(self) -> None:
        """DRAFT can be archived directly."""
        evaluation = _make_evaluation()
        evaluation.archive()
        assert evaluation.status == EvaluationStatus.ARCHIVED

    def test_archive_raises_event(self) -> None:
        """Archive raises EvaluationDefinitionArchived event."""
        evaluation = _make_evaluation()
        evaluation.collect_events()  # clear create event
        evaluation.archive()
        events = evaluation.collect_events()
        assert any(isinstance(e, EvaluationDefinitionArchived) for e in events)

    def test_already_archived_raises(self) -> None:
        """Archiving an archived evaluation raises ConflictError."""
        evaluation = _make_evaluation()
        evaluation.archive()
        with pytest.raises(ConflictError, match="already archived"):
            evaluation.archive()


class TestEvaluationDelete:
    """Tests for Evaluation.delete method."""

    def test_delete_raises_event(self) -> None:
        """Delete raises EvaluationDefinitionDeleted event."""
        evaluation = _make_evaluation()
        evaluation.collect_events()  # clear create event
        evaluation.delete()
        events = evaluation.collect_events()
        assert any(isinstance(e, EvaluationDefinitionDeleted) for e in events)

    def test_archived_cannot_delete(self) -> None:
        """Archived evaluation raises ConflictError on delete."""
        evaluation = _make_evaluation()
        evaluation.archive()
        with pytest.raises(ConflictError, match="Archived"):
            evaluation.delete()


class TestEvaluationDuplicate:
    """Tests for Evaluation.duplicate method."""

    def test_duplicate_creates_new_evaluation(self) -> None:
        """Duplicate creates a new Evaluation with DRAFT status."""
        evaluation = _make_evaluation(name="original")
        duplicate = evaluation.duplicate(EvaluationName(value="copy"))
        assert duplicate.id != evaluation.id
        assert duplicate.status == EvaluationStatus.DRAFT
        assert str(duplicate.name.value) == "copy"

    def test_duplicate_preserves_fields(self) -> None:
        """Duplicate copies all configuration fields."""
        evaluation = _make_evaluation()
        evaluation.update(
            description=EvaluationDescription(value="desc"),
            tags=("tag1",),
            configuration={"key": "value"},
        )
        duplicate = evaluation.duplicate(EvaluationName(value="copy"))
        assert duplicate.project_id == evaluation.project_id
        assert duplicate.provider == evaluation.provider
        assert duplicate.model == evaluation.model
        assert duplicate.metrics == evaluation.metrics
        assert duplicate.tags == ("tag1",)
        assert duplicate.configuration == {"key": "value"}

    def test_duplicate_raises_event(self) -> None:
        """Duplicate raises EvaluationDefinitionDuplicated event."""
        evaluation = _make_evaluation()
        evaluation.collect_events()  # clear create event
        duplicate = evaluation.duplicate(EvaluationName(value="copy"))
        events = duplicate.collect_events()
        assert any(isinstance(e, EvaluationDefinitionDuplicated) for e in events)

    def test_duplicate_is_independent(self) -> None:
        """Modifying duplicate does not affect original."""
        evaluation = _make_evaluation(name="original")
        duplicate = evaluation.duplicate(EvaluationName(value="copy"))
        duplicate.update(name=EvaluationName(value="modified"))
        assert str(evaluation.name.value) == "original"
