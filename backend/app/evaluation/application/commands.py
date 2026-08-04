"""Commands and queries for evaluation management."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CreateEvaluationCommand:
    """Command to create a new evaluation definition."""

    project_id: str
    dataset_id: str | None
    name: str
    description: str | None = None
    provider: str = ""
    model: str = ""
    metrics: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    configuration: dict[str, object] = field(default_factory=dict)
    created_by: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateEvaluationCommand:
    """Command to update an existing evaluation definition."""

    evaluation_id: str
    name: str | None = None
    description: str | None = None
    provider: str | None = None
    model: str | None = None
    metrics: tuple[str, ...] | None = None
    tags: tuple[str, ...] | None = None
    configuration: dict[str, object] | None = None
    dataset_id: str | None = None


@dataclass(frozen=True, slots=True)
class DeleteEvaluationCommand:
    """Command to delete an evaluation definition."""

    evaluation_id: str


@dataclass(frozen=True, slots=True)
class DuplicateEvaluationCommand:
    """Command to duplicate an evaluation definition."""

    evaluation_id: str
    new_name: str


@dataclass(frozen=True, slots=True)
class ArchiveEvaluationCommand:
    """Command to archive an evaluation definition."""

    evaluation_id: str


@dataclass(frozen=True, slots=True)
class MarkReadyEvaluationCommand:
    """Command to mark an evaluation as ready."""

    evaluation_id: str


@dataclass(frozen=True, slots=True)
class GetEvaluationQuery:
    """Query to retrieve a single evaluation by ID."""

    evaluation_id: str


@dataclass(frozen=True, slots=True)
class ListEvaluationsQuery:
    """Query to list evaluations with filtering and pagination."""

    project_id: str | None = None
    provider: str | None = None
    model: str | None = None
    status: str | None = None
    search: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20
