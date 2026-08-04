"""Pydantic schemas for agent API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateAgentRequest(BaseModel):
    """Request body for creating an agent."""

    project_id: str = Field(..., description="Project identifier")
    name: str = Field(..., min_length=1, max_length=255, description="Agent name")
    description: str | None = Field(default=None, max_length=2000, description="Description")
    agent_type: str = Field(default="llm", description="Agent type (llm, tool, hybrid, custom)")
    model: str = Field(..., min_length=1, description="Model identifier")
    provider: str = Field(..., min_length=1, description="Provider identifier")
    capabilities: list[str] = Field(default_factory=list, description="Capability tags")
    config: dict[str, object] = Field(
        default_factory=dict,
        description="Model configuration",
    )
    endpoint: str | None = Field(default=None, description="Custom endpoint URL")
    created_by: str | None = Field(default=None, description="Creator identifier")


class UpdateAgentRequest(BaseModel):
    """Request body for updating an agent."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    agent_type: str | None = None
    model: str | None = Field(default=None, min_length=1)
    provider: str | None = Field(default=None, min_length=1)
    capabilities: list[str] | None = None
    config: dict[str, object] | None = None
    endpoint: str | None = None


class AgentResponse(BaseModel):
    """Response model for a single agent."""

    id: str = Field(..., description="Agent identifier")
    project_id: str = Field(..., description="Project identifier")
    name: str = Field(..., description="Agent name")
    description: str | None = Field(default=None, description="Description")
    agent_type: str = Field(..., description="Agent type")
    model: str = Field(..., description="Model identifier")
    provider: str = Field(..., description="Provider identifier")
    capabilities: list[str] = Field(default_factory=list, description="Capability tags")
    config: dict[str, object] = Field(default_factory=dict, description="Model configuration")
    endpoint: str | None = Field(default=None, description="Custom endpoint URL")
    status: str = Field(..., description="Lifecycle status")
    created_by: str | None = Field(default=None, description="Creator")
    version: int = Field(..., description="Optimistic version")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class AgentSummaryResponse(BaseModel):
    """Summary response for agent lists."""

    id: str
    project_id: str
    name: str
    agent_type: str
    model: str
    provider: str
    status: str
    created_at: str
    updated_at: str


class AgentListResponse(BaseModel):
    """Paginated list response for agents."""

    items: list[AgentSummaryResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total matching agents")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
