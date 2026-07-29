"""Immutable value objects for the Evaluation domain."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.evaluation.domain.enums.evaluation_enums import EvaluationType, Priority

_MAX_TEMPERATURE: float = 2.0


@dataclass(frozen=True, slots=True)
class DatasetReference:
    """Reference to a dataset used by an evaluation."""

    dataset_id: str
    row_count: int
    version: str | None = None

    def __post_init__(self) -> None:
        """Validate dataset reference invariants."""
        if not self.dataset_id:
            msg = "Dataset ID cannot be empty"
            raise ValueError(msg)
        if self.row_count < 0:
            msg = "Row count cannot be negative"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ExecutionBudget:
    """Budget constraints for an evaluation run."""

    max_cost_usd: float | None = None
    max_tokens: int | None = None
    max_duration_seconds: int | None = None

    def __post_init__(self) -> None:
        """Validate budget invariants."""
        if self.max_cost_usd is not None and self.max_cost_usd < 0:
            msg = "Max cost cannot be negative"
            raise ValueError(msg)
        if self.max_tokens is not None and self.max_tokens < 0:
            msg = "Max tokens cannot be negative"
            raise ValueError(msg)
        if self.max_duration_seconds is not None and self.max_duration_seconds <= 0:
            msg = "Max duration must be positive"
            raise ValueError(msg)

    @property
    def is_unlimited(self) -> bool:
        """Return True if all budget dimensions are unlimited."""
        return (
            self.max_cost_usd is None
            and self.max_tokens is None
            and self.max_duration_seconds is None
        )


@dataclass(frozen=True, slots=True)
class ExecutionLimits:
    """Execution limits controlling concurrency and batching."""

    max_concurrency: int = 1
    batch_size: int = 50
    checkpoint_interval: int = 50

    def __post_init__(self) -> None:
        """Validate execution limits invariants."""
        if self.max_concurrency < 1:
            msg = "Max concurrency must be >= 1"
            raise ValueError(msg)
        if self.batch_size < 1:
            msg = "Batch size must be >= 1"
            raise ValueError(msg)
        if self.checkpoint_interval < 1:
            msg = "Checkpoint interval must be >= 1"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    """Policy controlling failure handling and continuation behavior."""

    continue_on_item_failure: bool = True
    max_retries_per_item: int = 0
    timeout_per_item_seconds: int | None = None

    def __post_init__(self) -> None:
        """Validate execution policy invariants."""
        if self.max_retries_per_item < 0:
            msg = "Max retries cannot be negative"
            raise ValueError(msg)
        if self.timeout_per_item_seconds is not None and self.timeout_per_item_seconds <= 0:
            msg = "Per-item timeout must be positive"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class EvaluationProfile:
    """Resolved execution profile for an evaluation run."""

    provider_name: str
    model_id: str
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout_seconds: int = 60
    system_prompt: str | None = None

    def __post_init__(self) -> None:
        """Validate profile invariants."""
        if not self.provider_name:
            msg = "Provider name cannot be empty"
            raise ValueError(msg)
        if not self.model_id:
            msg = "Model ID cannot be empty"
            raise ValueError(msg)
        if not (0.0 <= self.temperature <= _MAX_TEMPERATURE):
            msg = "Temperature must be between 0.0 and 2.0"
            raise ValueError(msg)
        if self.max_tokens < 1:
            msg = "Max tokens must be >= 1"
            raise ValueError(msg)
        if self.timeout_seconds <= 0:
            msg = "Timeout must be positive"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class EvaluationConfiguration:
    """Complete configuration for an evaluation."""

    name: str
    eval_type: EvaluationType
    profile: EvaluationProfile
    dataset: DatasetReference | None = None
    metrics: tuple[str, ...] = ()
    budget: ExecutionBudget = field(default_factory=ExecutionBudget)
    limits: ExecutionLimits = field(default_factory=ExecutionLimits)
    policy: ExecutionPolicy = field(default_factory=ExecutionPolicy)
    priority: Priority = Priority.NORMAL

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        if not self.name:
            msg = "Evaluation name cannot be empty"
            raise ValueError(msg)
        if not self.metrics:
            msg = "At least one metric is required"
            raise ValueError(msg)
        if self.eval_type in _DATASET_REQUIRED_TYPES and self.dataset is None:
            msg = f"Evaluation type '{self.eval_type.value}' requires a dataset"
            raise ValueError(msg)


_DATASET_REQUIRED_TYPES: frozenset[EvaluationType] = frozenset(
    {
        EvaluationType.DATASET,
        EvaluationType.REGRESSION,
        EvaluationType.SAFETY,
        EvaluationType.RAG,
        EvaluationType.COMPARISON,
    }
)


@dataclass(frozen=True, slots=True)
class EvaluationMetadata:
    """Metadata associated with an evaluation."""

    project_id: str | None = None
    created_by: str | None = None
    tags: tuple[str, ...] = ()
    description: str | None = None


@dataclass(frozen=True, slots=True)
class FailureSummary:
    """Summary of failures encountered during evaluation."""

    total_items: int
    failed_items: int
    failure_reasons: dict[str, int] = field(default_factory=dict)
    first_failure: str | None = None
    last_failure: str | None = None

    @property
    def failure_rate(self) -> float:
        """Return failure rate as a fraction (0.0 to 1.0)."""
        if self.total_items == 0:
            return 0.0
        return self.failed_items / self.total_items

    @property
    def all_items_failed(self) -> bool:
        """Return True if every item failed."""
        return self.failed_items > 0 and self.failed_items == self.total_items
