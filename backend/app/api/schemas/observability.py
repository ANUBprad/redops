"""Pydantic schemas for observability endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TimelineEventResponse(BaseModel):
    event_id: str
    run_id: str
    event_type: str
    data: dict[str, Any]
    correlation_id: str | None = None
    occurred_at: datetime


class LogEntryResponse(BaseModel):
    log_id: str
    run_id: str
    level: str
    source: str
    message: str
    metadata: dict[str, Any]
    correlation_id: str | None = None
    timestamp: datetime


class LogEntryCreateRequest(BaseModel):
    level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARN|ERROR)$")
    source: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=10000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class PaginatedTimelineResponse(BaseModel):
    items: list[TimelineEventResponse]
    total: int


class PaginatedLogsResponse(BaseModel):
    items: list[LogEntryResponse]
    total: int
