"""Pydantic schemas for Scheduling."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateScheduleRequest(BaseModel):
    """Request body for creating a schedule."""

    name: str = Field(min_length=1, max_length=255)
    schedule_type: str
    cron_expression: str = Field(min_length=5, max_length=100)
    task_config: dict[str, object] | None = None
    project_id: str | None = None
    timezone: str = "UTC"


class ScheduleResponse(BaseModel):
    """Response for a schedule."""

    id: str
    name: str
    schedule_type: str
    cron_expression: str
    task_config: dict[str, object]
    organization_id: str | None = None
    project_id: str | None = None
    created_by: str | None = None
    timezone: str
    status: str
    last_run_at: str | None = None
    next_run_at: str | None = None
    run_count: int = 0
    failure_count: int = 0
    version: int = 1
    created_at: str
    updated_at: str
