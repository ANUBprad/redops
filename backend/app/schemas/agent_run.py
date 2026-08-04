"""Pydantic schemas for agent run API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateAgentRunRequest(BaseModel):
    """Request body for creating an agent run."""

    agent_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Agent name",
    )
    agent_definition_id: str | None = Field(
        default=None,
        description="Agent definition ID",
    )
    provider: str = Field(..., min_length=1, description="Provider identifier")
    model: str = Field(..., min_length=1, description="Model identifier")
    tools: list[str] = Field(default_factory=list, description="Tool identifiers")
    max_steps: int = Field(default=10, ge=1, description="Maximum execution steps")
    timeout_seconds: int = Field(default=300, ge=1, description="Timeout in seconds")
    project_id: str | None = Field(default=None, description="Project identifier")
    created_by: str | None = Field(default=None, description="Creator identifier")
    tags: list[str] = Field(default_factory=list, description="Tags")
    workflow_id: str | None = Field(default=None, description="Temporal workflow ID")


class CancelAgentRunRequest(BaseModel):
    """Request body for cancelling an agent run."""

    reason: str = Field(default="user_cancelled", description="Cancellation reason")
    force: bool = Field(default=False, description="Force immediate cancellation")


class AgentRunResponse(BaseModel):
    """Response model for a single agent run."""

    id: str = Field(..., description="Run identifier")
    agent_definition_id: str | None = Field(default=None, description="Agent definition ID")
    agent_name: str = Field(..., description="Agent name")
    workflow_id: str | None = Field(default=None, description="Workflow identifier")
    provider: str = Field(..., description="Provider identifier")
    model: str = Field(..., description="Model identifier")
    status: str = Field(..., description="Run status")
    priority: str = Field(..., description="Run priority")
    steps_total: int = Field(..., description="Total steps")
    steps_completed: int = Field(..., description="Completed steps")
    steps_failed: int = Field(..., description="Failed steps")
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


class AgentRunSummaryResponse(BaseModel):
    """Summary response for run lists."""

    id: str
    agent_definition_id: str | None = None
    agent_name: str
    provider: str
    model: str
    status: str
    progress: float
    steps_total: int
    steps_completed: int
    steps_failed: int
    cost: float
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str


class AgentRunListResponse(BaseModel):
    """Paginated list response for agent runs."""

    items: list[AgentRunSummaryResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total matching runs")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
