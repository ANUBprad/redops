"""Tests for evaluation factories."""

from __future__ import annotations

import pytest

from app.evaluation.domain.enums.evaluation_enums import EvaluationType, RunStatus
from app.evaluation.domain.factories.evaluation_factories import (
    AggregatedMetricsFactory,
    EvaluationConfigurationFactory,
    EvaluationItemFactory,
    EvaluationRunFactory,
    RunCheckpointFactory,
)
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    DatasetReference,
    EvaluationProfile,
)
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ValidationError


class TestEvaluationConfigurationFactory:
    """Tests for EvaluationConfigurationFactory."""

    def test_create_valid_single(self) -> None:
        """Create valid single evaluation config."""
        profile = EvaluationProfile(provider_name="openai", model_id="gpt-4")
        config = EvaluationConfigurationFactory.create(
            name="Test",
            eval_type=EvaluationType.SINGLE,
            profile=profile,
            metrics=("accuracy",),
        )
        assert config.name == "Test"
        assert config.eval_type == EvaluationType.SINGLE

    def test_create_valid_dataset(self) -> None:
        """Create valid dataset evaluation config."""
        profile = EvaluationProfile(provider_name="openai", model_id="gpt-4")
        dataset = DatasetReference(dataset_id="ds-001", row_count=100)
        config = EvaluationConfigurationFactory.create(
            name="Test",
            eval_type=EvaluationType.DATASET,
            profile=profile,
            dataset=dataset,
            metrics=("accuracy",),
        )
        assert config.dataset == dataset

    def test_empty_name_raises(self) -> None:
        """Empty name raises ValidationError."""
        profile = EvaluationProfile(provider_name="openai", model_id="gpt-4")
        with pytest.raises(ValidationError):
            EvaluationConfigurationFactory.create(
                name="",
                eval_type=EvaluationType.SINGLE,
                profile=profile,
                metrics=("accuracy",),
            )

    def test_whitespace_name_raises(self) -> None:
        """Whitespace-only name raises ValidationError."""
        profile = EvaluationProfile(provider_name="openai", model_id="gpt-4")
        with pytest.raises(ValidationError):
            EvaluationConfigurationFactory.create(
                name="   ",
                eval_type=EvaluationType.SINGLE,
                profile=profile,
                metrics=("accuracy",),
            )

    def test_no_metrics_raises(self) -> None:
        """No metrics raises ValidationError."""
        profile = EvaluationProfile(provider_name="openai", model_id="gpt-4")
        with pytest.raises(ValidationError):
            EvaluationConfigurationFactory.create(
                name="Test",
                eval_type=EvaluationType.SINGLE,
                profile=profile,
                metrics=(),
            )

    def test_dataset_type_requires_dataset(self) -> None:
        """Dataset type without dataset raises ValidationError."""
        profile = EvaluationProfile(provider_name="openai", model_id="gpt-4")
        with pytest.raises(ValidationError):
            EvaluationConfigurationFactory.create(
                name="Test",
                eval_type=EvaluationType.DATASET,
                profile=profile,
                metrics=("accuracy",),
            )

    def test_single_type_no_dataset_needed(self) -> None:
        """Single type does not require dataset."""
        profile = EvaluationProfile(provider_name="openai", model_id="gpt-4")
        config = EvaluationConfigurationFactory.create(
            name="Test",
            eval_type=EvaluationType.SINGLE,
            profile=profile,
            metrics=("accuracy",),
        )
        assert config.dataset is None


class TestEvaluationRunFactory:
    """Tests for EvaluationRunFactory."""

    def test_create(self) -> None:
        """Create a run in CREATED state."""
        profile = EvaluationProfile(provider_name="openai", model_id="gpt-4")
        config = EvaluationConfigurationFactory.create(
            name="Test",
            eval_type=EvaluationType.SINGLE,
            profile=profile,
            metrics=("accuracy",),
        )
        run = EvaluationRunFactory.create(config=config, profile=profile)
        assert run.status == RunStatus.CREATED
        assert run.evaluation_name == "Test"

    def test_create_queued(self) -> None:
        """Create a run in QUEUED state."""
        profile = EvaluationProfile(provider_name="openai", model_id="gpt-4")
        config = EvaluationConfigurationFactory.create(
            name="Test",
            eval_type=EvaluationType.SINGLE,
            profile=profile,
            metrics=("accuracy",),
        )
        run = EvaluationRunFactory.create_queued(config=config, profile=profile)
        assert run.status == RunStatus.QUEUED


class TestEvaluationItemFactory:
    """Tests for EvaluationItemFactory."""

    def test_create_valid(self) -> None:
        """Create valid item."""
        run_id = UUIDv7.generate()
        item = EvaluationItemFactory.create(
            run_id=run_id,
            index=0,
            data={"input": "test"},
        )
        assert item.run_id == run_id
        assert item.index == 0

    def test_negative_index_raises(self) -> None:
        """Negative index raises ValidationError."""
        with pytest.raises(ValidationError):
            EvaluationItemFactory.create(
                run_id=UUIDv7.generate(),
                index=-1,
            )

    def test_zero_index_valid(self) -> None:
        """Zero index is valid."""
        item = EvaluationItemFactory.create(
            run_id=UUIDv7.generate(),
            index=0,
        )
        assert item.index == 0


class TestRunCheckpointFactory:
    """Tests for RunCheckpointFactory."""

    def test_create_valid(self) -> None:
        """Create valid checkpoint."""
        run_id = UUIDv7.generate()
        checkpoint = RunCheckpointFactory.create(
            run_id=run_id,
            checkpoint_number=1,
            items_completed=50,
            items_total=100,
            last_item_index=49,
        )
        assert checkpoint.checkpoint_number == 1
        assert checkpoint.items_completed == 50

    def test_negative_checkpoint_number_raises(self) -> None:
        """Negative checkpoint number raises ValidationError."""
        with pytest.raises(ValidationError):
            RunCheckpointFactory.create(
                run_id=UUIDv7.generate(),
                checkpoint_number=-1,
                items_completed=0,
                items_total=100,
                last_item_index=-1,
            )

    def test_negative_items_completed_raises(self) -> None:
        """Negative items_completed raises ValidationError."""
        with pytest.raises(ValidationError):
            RunCheckpointFactory.create(
                run_id=UUIDv7.generate(),
                checkpoint_number=0,
                items_completed=-1,
                items_total=100,
                last_item_index=-1,
            )

    def test_items_exceed_total_raises(self) -> None:
        """Items completed exceeding total raises ValidationError."""
        with pytest.raises(ValidationError):
            RunCheckpointFactory.create(
                run_id=UUIDv7.generate(),
                checkpoint_number=0,
                items_completed=101,
                items_total=100,
                last_item_index=100,
            )

    def test_negative_last_index_raises(self) -> None:
        """Last item index < -1 raises ValidationError."""
        with pytest.raises(ValidationError):
            RunCheckpointFactory.create(
                run_id=UUIDv7.generate(),
                checkpoint_number=0,
                items_completed=0,
                items_total=100,
                last_item_index=-2,
            )


class TestAggregatedMetricsFactory:
    """Tests for AggregatedMetricsFactory."""

    def test_from_scores(self) -> None:
        """Create metrics from scores."""
        metrics = AggregatedMetricsFactory.from_scores("accuracy", [0.8, 0.9, 0.7])
        assert metrics.metric_name == "accuracy"
        assert metrics.item_count == 3

    def test_from_item_results(self) -> None:
        """Create metrics from item results."""
        from app.evaluation.domain.entities.evaluation_entities import ItemResult
        from app.evaluation.domain.enums.evaluation_enums import ItemStatus

        results = (
            ItemResult(
                item_id=UUIDv7.generate(),
                item_index=0,
                scores={"accuracy": 0.9},
                status=ItemStatus.COMPLETED,
            ),
            ItemResult(
                item_id=UUIDv7.generate(),
                item_index=1,
                scores={"accuracy": 0.8},
                status=ItemStatus.COMPLETED,
            ),
        )
        metrics = AggregatedMetricsFactory.from_item_results("accuracy", results)
        assert metrics.item_count == 2
        assert metrics.partial is False
