"""Commands and queries for evaluation run management."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateEvaluationRunCommand:
    """Command to create a new evaluation run."""

    evaluation_id: str | None = None
    evaluation_name: str = ""
    config_name: str = ""
    eval_type: str = "single"
    provider: str = ""
    model: str = ""
    metrics: tuple[str, ...] = ()
    project_id: str | None = None
    created_by: str | None = None
    tags: tuple[str, ...] = ()
    workflow_id: str | None = None


@dataclass(frozen=True, slots=True)
class QueueEvaluationRunCommand:
    """Command to queue a run for execution."""

    run_id: str


@dataclass(frozen=True, slots=True)
class StartEvaluationRunCommand:
    """Command to start a queued run."""

    run_id: str
    total_items: int


@dataclass(frozen=True, slots=True)
class UpdateRunProgressCommand:
    """Command to update run progress."""

    run_id: str
    items_completed: int = 0
    items_failed: int = 0
    token_input: int = 0
    token_output: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


@dataclass(frozen=True, slots=True)
class CompleteEvaluationRunCommand:
    """Command to mark a run as completed."""

    run_id: str


@dataclass(frozen=True, slots=True)
class FailEvaluationRunCommand:
    """Command to mark a run as failed."""

    run_id: str
    error_code: str = ""
    error_message: str = ""


@dataclass(frozen=True, slots=True)
class CancelEvaluationRunCommand:
    """Command to cancel a run."""

    run_id: str
    reason: str = "user_cancelled"
    force: bool = False


@dataclass(frozen=True, slots=True)
class RetryEvaluationRunCommand:
    """Command to retry a failed run."""

    run_id: str


@dataclass(frozen=True, slots=True)
class GetEvaluationRunQuery:
    """Query to retrieve a single run by ID."""

    run_id: str


@dataclass(frozen=True, slots=True)
class ListEvaluationRunsQuery:
    """Query to list runs with filtering and pagination."""

    evaluation_id: str | None = None
    status: str | None = None
    provider: str | None = None
    model: str | None = None
    search: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20
