"""Audit domain entity and value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from app.kernel.entities.base import UUIDv7


class AuditAction(StrEnum):
    """Types of auditable actions."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    REGISTER = "register"
    INVITE = "invite"
    ACCEPT_INVITATION = "accept_invitation"
    REMOVE_MEMBER = "remove_member"
    CHANGE_ROLE = "change_role"
    EXPORT = "export"
    EXECUTE = "execute"
    CANCEL = "cancel"
    REVOKE = "revoke"
    ROTATE = "rotate"
    VERIFY = "verify"
    RESET_PASSWORD = "reset_password"
    SCHEDULE = "schedule"
    NOTIFY = "notify"


class AuditResourceType(StrEnum):
    """Types of resources that can be audited."""

    USER = "user"
    ORGANIZATION = "organization"
    PROJECT = "project"
    EVALUATION = "evaluation"
    EVALUATION_RUN = "evaluation_run"
    METRIC = "metric"
    REPORT = "report"
    RED_TEAM = "red_team"
    ATTACK_RUN = "attack_run"
    API_KEY = "api_key"
    SCHEDULE = "schedule"
    NOTIFICATION = "notification"
    INVITATION = "invitation"
    MEMBERSHIP = "membership"
    SETTINGS = "settings"


@dataclass(frozen=True, slots=True)
class AuditLog:
    """Immutable audit log entry."""

    log_id: str = field(default_factory=lambda: str(UUIDv7.generate()))
    user_id: str = ""
    user_email: str = ""
    action: str = ""
    resource_type: str = ""
    resource_id: str = ""
    organization_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    request_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        user_id: str,
        user_email: str = "",
        action: str,
        resource_type: str,
        resource_id: str = "",
        organization_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, object] | None = None,
        request_id: str | None = None,
    ) -> AuditLog:
        return cls(
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            organization_id=organization_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {},
            request_id=request_id,
        )
