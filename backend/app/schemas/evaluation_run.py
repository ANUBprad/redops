"""Pydantic schemas for evaluation run API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DatasetItemRequest(BaseModel):
    """A single dataset item supplied at run creation.

    Attributes:
        prompt: The prompt sent to the provider.
        reference: Optional reference answer for reference-based metrics.
        context: Optional context provided to the model.
        id: Optional stable item identifier.

    """

    prompt: str = Field(..., min_length=1, description="Prompt sent to the provider")
    reference: str | None = Field(default=None, description="Reference answer")
    context: str | None = Field(default=None, description="Item context")
    id: str | None = Field(default=None, description="Stable item identifier")


class CreateEvaluationRunRequest(BaseModel):
    """Request body for creating an evaluation run."""

    evaluation_id: str | None = Field(
        default=None,
        description="Parent evaluation definition ID",
    )
    evaluation_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Evaluation name",
    )
    provider: str = Field(..., min_length=1, description="Provider identifier")
    model: str = Field(..., min_length=1, description="Model identifier")
    metrics: list[str] = Field(default_factory=list, description="Metric identifiers")
    project_id: str | None = Field(default=None, description="Project identifier")
    created_by: str | None = Field(default=None, description="Creator identifier")
    tags: list[str] = Field(default_factory=list, description="Tags")
    workflow_id: str | None = Field(default=None, description="Temporal workflow ID")
    total_items: int = Field(default=0, ge=0, description="Total items to evaluate")
    system_prompt: str | None = Field(
        default=None,
        description="System prompt prepended to provider calls",
    )
    prompt_template: str | None = Field(
        default=None,
        description="Prompt template with {variable} placeholders",
    )
    dataset_items: list[DatasetItemRequest] = Field(
        default_factory=list,
        description="Dataset items to evaluate",
    )


class CancelRunRequest(BaseModel):
    """Request body for cancelling a run."""

    reason: str = Field(default="user_cancelled", description="Cancellation reason")
    force: bool = Field(default=False, description="Force immediate cancellation")


class RunResponse(BaseModel):
    """Response model for a single evaluation run."""

    id: str = Field(..., description="Run identifier")
    evaluation_id: str | None = Field(default=None, description="Parent evaluation ID")
    evaluation_name: str = Field(..., description="Evaluation name")
    workflow_id: str | None = Field(default=None, description="Workflow identifier")
    provider: str = Field(..., description="Provider identifier")
    model: str = Field(..., description="Model identifier")
    status: str = Field(..., description="Run status")
    priority: str = Field(..., description="Run priority")
    items_total: int = Field(..., description="Total items")
    items_completed: int = Field(..., description="Completed items")
    items_failed: int = Field(..., description="Failed items")
    progress: float = Field(..., description="Completion percentage")
    token_input: int = Field(..., description="Input tokens")
    token_output: int = Field(..., description="Output tokens")
    total_tokens: int = Field(..., description="Total tokens")
    cost: float = Field(..., description="Total cost in USD")
    average_latency_ms: int = Field(..., description="Average latency in ms")
    failure_reason: str | None = Field(default=None, description="Failure reason")
    version: int = Field(..., description="Optimistic version")
    started_at: str | None = Field(default=None, description="Start timestamp")
    completed_at: str | None = Field(default=None, description="Completion timestamp")
    cancelled_at: str | None = Field(default=None, description="Cancellation timestamp")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class RunSummaryResponse(BaseModel):
    """Summary response for run lists."""

    id: str
    evaluation_id: str | None = None
    evaluation_name: str
    provider: str
    model: str
    status: str
    progress: float
    items_total: int
    items_completed: int
    items_failed: int
    cost: float
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str


class RunListResponse(BaseModel):
    """Paginated list response for runs."""

    items: list[RunSummaryResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total matching runs")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
