"""Pydantic schemas for Audit API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    """Response for an audit log entry."""

    log_id: str
    user_id: str
    user_email: str
    action: str
    resource_type: str
    resource_id: str
    organization_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    timestamp: str
    request_id: str | None = None


class AuditLogListResponse(BaseModel):
    """Paginated list of audit logs."""

    items: list[AuditLogResponse]
    total: int
    offset: int
    limit: int
