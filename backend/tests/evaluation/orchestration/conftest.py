"""Shared fixtures for evaluation orchestration tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.evaluation.domain.enums.evaluation_enums import EvaluationType, Priority
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    DatasetReference,
    EvaluationConfiguration,
    EvaluationMetadata,
    EvaluationProfile,
    ExecutionBudget,
    ExecutionLimits,
    ExecutionPolicy,
)
from app.evaluation.execution.context.context import (
    CancellationToken,
    MetricSelection,
    PipelineContext,
    ProviderSelection,
    TraceIdentifiers,
)
from app.kernel.entities.base import UUIDv7

# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_profile() -> EvaluationProfile:
    """Standard evaluation profile."""
    return EvaluationProfile(
        provider_name="openai",
        model_id="gpt-4",
        temperature=0.0,
        max_tokens=4096,
        timeout_seconds=60,
    )


@pytest.fixture()
def sample_dataset() -> DatasetReference:
    """Standard dataset reference with 10 rows."""
    return DatasetReference(dataset_id="ds-001", row_count=10)


@pytest.fixture()
def sample_config(
    sample_profile: EvaluationProfile, sample_dataset: DatasetReference
) -> EvaluationConfiguration:
    """Standard dataset evaluation configuration."""
    return EvaluationConfiguration(
        name="Test Evaluation",
        eval_type=EvaluationType.DATASET,
        profile=sample_profile,
        dataset=sample_dataset,
        metrics=("accuracy", "relevance"),
        budget=ExecutionBudget(max_cost_usd=100.0, max_tokens=100_000, max_duration_seconds=3600),
        limits=ExecutionLimits(max_concurrency=1, batch_size=50, checkpoint_interval=5),
        policy=ExecutionPolicy(
            continue_on_item_failure=True, max_retries_per_item=0, timeout_per_item_seconds=30
        ),
        priority=Priority.NORMAL,
    )


@pytest.fixture()
def single_config(sample_profile: EvaluationProfile) -> EvaluationConfiguration:
    """Single-type evaluation configuration (no dataset)."""
    return EvaluationConfiguration(
        name="Single Eval",
        eval_type=EvaluationType.SINGLE,
        profile=sample_profile,
        metrics=("accuracy",),
    )


@pytest.fixture()
def sample_metadata() -> EvaluationMetadata:
    """Standard evaluation metadata."""
    return EvaluationMetadata(
        project_id="proj-001",
        created_by="test-user",
        tags=("smoke",),
        description="A test evaluation",
    )


# ---------------------------------------------------------------------------
# Domain Entities
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_run(
    sample_config: EvaluationConfiguration, sample_profile: EvaluationProfile
) -> EvaluationRun:
    """Standard EvaluationRun in CREATED state."""
    from app.evaluation.domain.entities.evaluation_entities import EvaluationRun

    return EvaluationRun(
        evaluation_name=sample_config.name,
        config=sample_config,
        profile=sample_profile,
    )


@pytest.fixture()
def queued_run(
    sample_config: EvaluationConfiguration, sample_profile: EvaluationProfile
) -> EvaluationRun:
    """EvaluationRun in QUEUED state."""
    from app.evaluation.domain.entities.evaluation_entities import EvaluationRun

    run = EvaluationRun(
        evaluation_name=sample_config.name,
        config=sample_config,
        profile=sample_profile,
    )
    run.queue()
    return run


@pytest.fixture()
def running_run(
    sample_config: EvaluationConfiguration, sample_profile: EvaluationProfile
) -> EvaluationRun:
    """EvaluationRun in RUNNING state with 10 items."""
    from app.evaluation.domain.entities.evaluation_entities import EvaluationRun

    run = EvaluationRun(
        evaluation_name=sample_config.name,
        config=sample_config,
        profile=sample_profile,
    )
    run.queue()
    run.start(total_items=10)
    return run


# ---------------------------------------------------------------------------
# Pipeline Context
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_run_id() -> UUIDv7:
    """A sample run ID."""
    return UUIDv7.generate()


@pytest.fixture()
def sample_context(sample_run_id: UUIDv7) -> PipelineContext:
    """Standard PipelineContext."""
    return PipelineContext(
        run_id=sample_run_id,
        evaluation_name="Test Eval",
        provider_selection=ProviderSelection(provider_name="openai", model_id="gpt-4"),
        metric_selection=MetricSelection(metric_names=("accuracy",)),
        trace=TraceIdentifiers.from_correlation_id(str(sample_run_id)),
    )


@pytest.fixture()
def cancelled_context(sample_run_id: UUIDv7) -> PipelineContext:
    """PipelineContext with cancellation requested."""
    return PipelineContext(
        run_id=sample_run_id,
        evaluation_name="Test Eval",
        provider_selection=ProviderSelection(provider_name="openai", model_id="gpt-4"),
        metric_selection=MetricSelection(metric_names=("accuracy",)),
        cancellation_token=CancellationToken(cancelled=True, force=True),
        trace=TraceIdentifiers.from_correlation_id(str(sample_run_id)),
    )


# ---------------------------------------------------------------------------
# Mock Dependencies
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_event_publisher() -> MagicMock:
    """Mock EventPublisher."""
    mock = MagicMock()
    mock.publish = MagicMock()
    mock.publish_many = MagicMock()
    return mock


@pytest.fixture()
def mock_run_repository() -> MagicMock:
    """Mock RunRepository."""
    mock = MagicMock()
    mock.save = MagicMock()
    mock.find_by_id = MagicMock(return_value=None)
    mock.find_by_status = MagicMock(return_value=[])
    mock.delete = MagicMock(return_value=True)
    return mock


@pytest.fixture()
def mock_item_repository() -> MagicMock:
    """Mock ItemRepository."""
    mock = MagicMock()
    mock.save_many = MagicMock()
    mock.find_by_run_id = MagicMock(return_value=[])
    mock.find_pending_by_run_id = MagicMock(return_value=[])
    return mock


@pytest.fixture()
def mock_checkpoint_repository() -> MagicMock:
    """Mock CheckpointRepository."""
    mock = MagicMock()
    mock.save = MagicMock()
    mock.find_latest = MagicMock(return_value=None)
    mock.find_by_number = MagicMock(return_value=None)
    mock.prune = MagicMock(return_value=0)
    return mock


@pytest.fixture()
def mock_provider_registry() -> MagicMock:
    """Mock ProviderRegistry."""
    mock = MagicMock()
    mock.is_registered = MagicMock(return_value=True)
    mock.resolve = MagicMock(return_value=MagicMock())
    return mock
