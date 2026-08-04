"""Tests for evaluation value objects."""

from __future__ import annotations

import pytest

from app.evaluation.domain.enums.evaluation_enums import EvaluationType
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    DatasetReference,
    EvaluationConfiguration,
    EvaluationMetadata,
    EvaluationProfile,
    ExecutionBudget,
    ExecutionLimits,
    ExecutionPolicy,
    FailureSummary,
)


class TestDatasetReference:
    """Tests for DatasetReference value object."""

    def test_valid_creation(self) -> None:
        """Valid dataset reference can be created."""
        ref = DatasetReference(dataset_id="ds-001", row_count=100)
        assert ref.dataset_id == "ds-001"
        assert ref.row_count == 100
        assert ref.version is None

    def test_with_version(self) -> None:
        """Dataset reference with version."""
        ref = DatasetReference(dataset_id="ds-001", row_count=50, version="v2")
        assert ref.version == "v2"

    def test_empty_dataset_id_raises(self) -> None:
        """Empty dataset ID raises ValueError."""
        with pytest.raises(ValueError, match="Dataset ID cannot be empty"):
            DatasetReference(dataset_id="", row_count=100)

    def test_negative_row_count_raises(self) -> None:
        """Negative row count raises ValueError."""
        with pytest.raises(ValueError, match="Row count cannot be negative"):
            DatasetReference(dataset_id="ds-001", row_count=-1)

    def test_zero_row_count_valid(self) -> None:
        """Zero row count is valid."""
        ref = DatasetReference(dataset_id="ds-001", row_count=0)
        assert ref.row_count == 0

    def test_equality(self) -> None:
        """Equal references are equal."""
        a = DatasetReference(dataset_id="ds-001", row_count=100)
        b = DatasetReference(dataset_id="ds-001", row_count=100)
        assert a == b

    def test_inequality(self) -> None:
        """Different references are not equal."""
        a = DatasetReference(dataset_id="ds-001", row_count=100)
        b = DatasetReference(dataset_id="ds-002", row_count=100)
        assert a != b

    def test_hashable(self) -> None:
        """Dataset reference can be used in sets."""
        a = DatasetReference(dataset_id="ds-001", row_count=100)
        b = DatasetReference(dataset_id="ds-001", row_count=100)
        assert len({a, b}) == 1


class TestExecutionBudget:
    """Tests for ExecutionBudget value object."""

    def test_unlimited(self) -> None:
        """Default budget is unlimited."""
        budget = ExecutionBudget()
        assert budget.is_unlimited is True

    def test_with_cost_limit(self) -> None:
        """Budget with cost limit."""
        budget = ExecutionBudget(max_cost_usd=10.0)
        assert budget.max_cost_usd == 10.0
        assert budget.is_unlimited is False

    def test_with_token_limit(self) -> None:
        """Budget with token limit."""
        budget = ExecutionBudget(max_tokens=100000)
        assert budget.max_tokens == 100000

    def test_with_duration_limit(self) -> None:
        """Budget with duration limit."""
        budget = ExecutionBudget(max_duration_seconds=3600)
        assert budget.max_duration_seconds == 3600

    def test_negative_cost_raises(self) -> None:
        """Negative cost limit raises ValueError."""
        with pytest.raises(ValueError, match="Max cost cannot be negative"):
            ExecutionBudget(max_cost_usd=-1.0)

    def test_negative_tokens_raises(self) -> None:
        """Negative token limit raises ValueError."""
        with pytest.raises(ValueError, match="Max tokens cannot be negative"):
            ExecutionBudget(max_tokens=-1)

    def test_zero_duration_raises(self) -> None:
        """Zero duration limit raises ValueError."""
        with pytest.raises(ValueError, match="Max duration must be positive"):
            ExecutionBudget(max_duration_seconds=0)

    def test_negative_duration_raises(self) -> None:
        """Negative duration limit raises ValueError."""
        with pytest.raises(ValueError, match="Max duration must be positive"):
            ExecutionBudget(max_duration_seconds=-1)


class TestExecutionLimits:
    """Tests for ExecutionLimits value object."""

    def test_defaults(self) -> None:
        """Default limits are sensible."""
        limits = ExecutionLimits()
        assert limits.max_concurrency == 1
        assert limits.batch_size == 50
        assert limits.checkpoint_interval == 50

    def test_custom_limits(self) -> None:
        """Custom limits can be set."""
        limits = ExecutionLimits(max_concurrency=10, batch_size=100, checkpoint_interval=25)
        assert limits.max_concurrency == 10
        assert limits.batch_size == 100
        assert limits.checkpoint_interval == 25

    def test_zero_concurrency_raises(self) -> None:
        """Zero concurrency raises ValueError."""
        with pytest.raises(ValueError, match="Max concurrency must be >= 1"):
            ExecutionLimits(max_concurrency=0)

    def test_zero_batch_size_raises(self) -> None:
        """Zero batch size raises ValueError."""
        with pytest.raises(ValueError, match="Batch size must be >= 1"):
            ExecutionLimits(batch_size=0)

    def test_zero_checkpoint_interval_raises(self) -> None:
        """Zero checkpoint interval raises ValueError."""
        with pytest.raises(ValueError, match="Checkpoint interval must be >= 1"):
            ExecutionLimits(checkpoint_interval=0)


class TestExecutionPolicy:
    """Tests for ExecutionPolicy value object."""

    def test_defaults(self) -> None:
        """Default policy is sensible."""
        policy = ExecutionPolicy()
        assert policy.continue_on_item_failure is True
        assert policy.max_retries_per_item == 0
        assert policy.timeout_per_item_seconds is None

    def test_custom_policy(self) -> None:
        """Custom policy can be set."""
        policy = ExecutionPolicy(
            continue_on_item_failure=False,
            max_retries_per_item=3,
            timeout_per_item_seconds=30,
        )
        assert policy.continue_on_item_failure is False
        assert policy.max_retries_per_item == 3
        assert policy.timeout_per_item_seconds == 30

    def test_negative_retries_raises(self) -> None:
        """Negative retries raises ValueError."""
        with pytest.raises(ValueError, match="Max retries cannot be negative"):
            ExecutionPolicy(max_retries_per_item=-1)

    def test_zero_timeout_raises(self) -> None:
        """Zero timeout raises ValueError."""
        with pytest.raises(ValueError, match="Per-item timeout must be positive"):
            ExecutionPolicy(timeout_per_item_seconds=0)

    def test_negative_timeout_raises(self) -> None:
        """Negative timeout raises ValueError."""
        with pytest.raises(ValueError, match="Per-item timeout must be positive"):
            ExecutionPolicy(timeout_per_item_seconds=-1)


class TestEvaluationProfile:
    """Tests for EvaluationProfile value object."""

    def test_valid_creation(self) -> None:
        """Valid profile can be created."""
        profile = EvaluationProfile(provider_name="openai", model_id="gpt-4")
        assert profile.provider_name == "openai"
        assert profile.model_id == "gpt-4"
        assert profile.temperature == 0.0
        assert profile.max_tokens == 4096
        assert profile.timeout_seconds == 60

    def test_empty_provider_allowed(self) -> None:
        """Empty provider name is allowed in shared profile type."""
        profile = EvaluationProfile(provider_name="", model_id="gpt-4")
        assert profile.provider_name == ""

    def test_empty_model_allowed(self) -> None:
        """Empty model ID is allowed in shared profile type."""
        profile = EvaluationProfile(provider_name="openai", model_id="")
        assert profile.model_id == ""

    def test_extreme_temperature_allowed(self) -> None:
        """Extreme temperatures are allowed in shared profile type."""
        profile = EvaluationProfile(provider_name="openai", model_id="gpt-4", temperature=3.0)
        assert profile.temperature == 3.0

    def test_zero_max_tokens_allowed(self) -> None:
        """Zero max tokens is allowed in shared profile type."""
        profile = EvaluationProfile(provider_name="openai", model_id="gpt-4", max_tokens=0)
        assert profile.max_tokens == 0

    def test_zero_timeout_allowed(self) -> None:
        """Zero timeout is allowed in shared profile type."""
        profile = EvaluationProfile(provider_name="openai", model_id="gpt-4", timeout_seconds=0)
        assert profile.timeout_seconds == 0


class TestEvaluationConfiguration:
    """Tests for EvaluationConfiguration value object."""

    def _make_config(self, **kwargs) -> EvaluationConfiguration:
        """Helper to create a valid configuration."""
        defaults = {
            "name": "Test Evaluation",
            "eval_type": EvaluationType.SINGLE,
            "profile": EvaluationProfile(provider_name="openai", model_id="gpt-4"),
            "metrics": ("accuracy",),
        }
        defaults.update(kwargs)
        return EvaluationConfiguration(**defaults)

    def test_valid_single(self) -> None:
        """Valid single evaluation config."""
        config = self._make_config()
        assert config.name == "Test Evaluation"
        assert config.eval_type == EvaluationType.SINGLE

    def test_empty_name_raises(self) -> None:
        """Empty name raises ValueError."""
        with pytest.raises(ValueError, match="Evaluation name cannot be empty"):
            self._make_config(name="")

    def test_no_metrics_raises(self) -> None:
        """No metrics raises ValueError."""
        with pytest.raises(ValueError, match="At least one metric is required"):
            self._make_config(metrics=())

    def test_dataset_required_for_dataset_type(self) -> None:
        """Dataset type requires dataset reference."""
        with pytest.raises(ValueError, match="requires a dataset"):
            self._make_config(
                eval_type=EvaluationType.DATASET,
                dataset=None,
            )

    def test_dataset_not_required_for_single(self) -> None:
        """Single type does not require dataset."""
        config = self._make_config(eval_type=EvaluationType.SINGLE, dataset=None)
        assert config.dataset is None

    def test_dataset_provided(self) -> None:
        """Dataset type with dataset reference is valid."""
        dataset = DatasetReference(dataset_id="ds-001", row_count=100)
        config = self._make_config(
            eval_type=EvaluationType.DATASET,
            dataset=dataset,
        )
        assert config.dataset == dataset


class TestFailureSummary:
    """Tests for FailureSummary value object."""

    def test_empty_summary(self) -> None:
        """Empty summary has zero failure rate."""
        summary = FailureSummary(total_items=0, failed_items=0)
        assert summary.failure_rate == 0.0
        assert summary.all_items_failed is False

    def test_partial_failure(self) -> None:
        """Partial failure has correct rate."""
        summary = FailureSummary(total_items=100, failed_items=10)
        assert summary.failure_rate == 0.1
        assert summary.all_items_failed is False

    def test_all_items_failed(self) -> None:
        """All items failed."""
        summary = FailureSummary(total_items=100, failed_items=100)
        assert summary.failure_rate == 1.0
        assert summary.all_items_failed is True

    def test_failure_reasons(self) -> None:
        """Failure reasons are tracked."""
        summary = FailureSummary(
            total_items=10,
            failed_items=3,
            failure_reasons={"provider_error": 2, "timeout": 1},
        )
        assert summary.failure_reasons["provider_error"] == 2

    def test_first_and_last_failure(self) -> None:
        """First and last failure messages are tracked."""
        summary = FailureSummary(
            total_items=10,
            failed_items=2,
            first_failure="First error",
            last_failure="Last error",
        )
        assert summary.first_failure == "First error"
        assert summary.last_failure == "Last error"


class TestEvaluationMetadata:
    """Tests for EvaluationMetadata value object."""

    def test_defaults(self) -> None:
        """Default metadata has no values."""
        metadata = EvaluationMetadata()
        assert metadata.project_id is None
        assert metadata.created_by is None
        assert metadata.tags == ()
        assert metadata.description is None

    def test_with_values(self) -> None:
        """Metadata with values."""
        metadata = EvaluationMetadata(
            project_id="proj-001",
            created_by="user@example.com",
            tags=("safety", "gpt-4"),
            description="Test description",
        )
        assert metadata.project_id == "proj-001"
        assert len(metadata.tags) == 2
