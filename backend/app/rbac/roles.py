"""RBAC roles and permissions."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """System-wide roles for organization members."""

    OWNER = "owner"
    ADMIN = "admin"
    DEVELOPER = "developer"
    ANALYST = "analyst"
    VIEWER = "viewer"


class Permission(StrEnum):
    """Granular permissions for resources."""

    # Evaluations
    EVALUATION_CREATE = "evaluation:create"
    EVALUATION_READ = "evaluation:read"
    EVALUATION_UPDATE = "evaluation:update"
    EVALUATION_DELETE = "evaluation:delete"

    # Runs
    RUN_CREATE = "run:create"
    RUN_READ = "run:read"
    RUN_CANCEL = "run:cancel"
    RUN_DELETE = "run:delete"

    # Metrics
    METRIC_READ = "metric:read"
    METRIC_CREATE = "metric:create"
    METRIC_DELETE = "metric:delete"

    # Reports
    REPORT_READ = "report:read"
    REPORT_CREATE = "report:create"
    REPORT_EXPORT = "report:export"

    # Red Team
    REDTEAM_READ = "redteam:read"
    REDTEAM_CREATE = "redteam:create"
    REDTEAM_EXECUTE = "redteam:execute"
    REDTEAM_DELETE = "redteam:delete"

    # Analytics
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"

    # Datasets
    DATASET_READ = "dataset:read"
    DATASET_CREATE = "dataset:create"
    DATASET_UPDATE = "dataset:update"
    DATASET_DELETE = "dataset:delete"

    # Settings
    SETTINGS_READ = "settings:read"
    SETTINGS_UPDATE = "settings:update"

    # API Keys
    APIKEY_CREATE = "apikey:create"
    APIKEY_READ = "apikey:read"
    APIKEY_REVOKE = "apikey:revoke"

    # Organization
    ORG_MANAGE = "org:manage"
    ORG_INVITE = "org:invite"
    ORG_REMOVE_MEMBER = "org:remove_member"
    ORG_CHANGE_ROLE = "org:change_role"
