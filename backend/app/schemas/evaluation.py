"""Pydantic schemas for evaluation API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateEvaluationRequest(BaseModel):
    """Request body for creating an evaluation."""

    project_id: str = Field(..., description="Project identifier")
    dataset_id: str | None = Field(default=None, description="Dataset identifier")
    name: str = Field(..., min_length=1, max_length=255, description="Evaluation name")
    description: str | None = Field(default=None, max_length=2000, description="Description")
    provider: str = Field(..., min_length=1, description="Provider identifier")
    model: str = Field(..., min_length=1, description="Model identifier")
    metrics: list[str] = Field(default_factory=list, description="Metric identifiers")
    tags: list[str] = Field(default_factory=list, description="Tags")
    configuration: dict[str, object] = Field(
        default_factory=dict,
        description="Execution configuration",
    )
    created_by: str | None = Field(default=None, description="Creator identifier")


class UpdateEvaluationRequest(BaseModel):
    """Request body for updating an evaluation."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    provider: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    metrics: list[str] | None = None
    tags: list[str] | None = None
    configuration: dict[str, object] | None = None
    dataset_id: str | None = None


class DuplicateEvaluationRequest(BaseModel):
    """Request body for duplicating an evaluation."""

    name: str = Field(..., min_length=1, max_length=255, description="New evaluation name")


class EvaluationResponse(BaseModel):
    """Response model for a single evaluation."""

    id: str = Field(..., description="Evaluation identifier")
    project_id: str = Field(..., description="Project identifier")
    dataset_id: str | None = Field(default=None, description="Dataset identifier")
    name: str = Field(..., description="Evaluation name")
    description: str | None = Field(default=None, description="Description")
    provider: str = Field(..., description="Provider identifier")
    model: str = Field(..., description="Model identifier")
    metrics: list[str] = Field(default_factory=list, description="Metric identifiers")
    tags: list[str] = Field(default_factory=list, description="Tags")
    configuration: dict[str, object] = Field(default_factory=dict, description="Configuration")
    status: str = Field(..., description="Lifecycle status")
    created_by: str | None = Field(default=None, description="Creator")
    version: int = Field(..., description="Optimistic version")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class EvaluationSummaryResponse(BaseModel):
    """Summary response for evaluation lists."""

    id: str
    project_id: str
    name: str
    provider: str
    model: str
    status: str
    tags: list[str]
    created_at: str
    updated_at: str


class EvaluationListResponse(BaseModel):
    """Paginated list response for evaluations."""

    items: list[EvaluationSummaryResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total matching evaluations")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
