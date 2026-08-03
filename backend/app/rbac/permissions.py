"""RBAC permission matrix."""

from __future__ import annotations

from app.rbac.roles import Permission, Role

__all__ = [
    "Permission",
    "Role",
    "get_permissions_for_role",
    "has_any_permission",
    "has_permission",
]

# Permission matrix: role -> set of permissions
PERMISSION_MATRIX: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),  # All permissions
    Role.ADMIN: frozenset(
        {
            Permission.EVALUATION_CREATE,
            Permission.EVALUATION_READ,
            Permission.EVALUATION_UPDATE,
            Permission.EVALUATION_DELETE,
            Permission.RUN_CREATE,
            Permission.RUN_READ,
            Permission.RUN_CANCEL,
            Permission.RUN_DELETE,
            Permission.METRIC_READ,
            Permission.METRIC_CREATE,
            Permission.METRIC_DELETE,
            Permission.REPORT_READ,
            Permission.REPORT_CREATE,
            Permission.REPORT_EXPORT,
            Permission.REDTEAM_READ,
            Permission.REDTEAM_CREATE,
            Permission.REDTEAM_EXECUTE,
            Permission.REDTEAM_DELETE,
            Permission.ANALYTICS_READ,
            Permission.ANALYTICS_EXPORT,
            Permission.DATASET_READ,
            Permission.DATASET_CREATE,
            Permission.DATASET_UPDATE,
            Permission.DATASET_DELETE,
            Permission.SETTINGS_READ,
            Permission.SETTINGS_UPDATE,
            Permission.APIKEY_CREATE,
            Permission.APIKEY_READ,
            Permission.APIKEY_REVOKE,
            Permission.ORG_INVITE,
            Permission.ORG_REMOVE_MEMBER,
            Permission.ORG_CHANGE_ROLE,
        }
    ),
    Role.DEVELOPER: frozenset(
        {
            Permission.EVALUATION_CREATE,
            Permission.EVALUATION_READ,
            Permission.EVALUATION_UPDATE,
            Permission.RUN_CREATE,
            Permission.RUN_READ,
            Permission.RUN_CANCEL,
            Permission.METRIC_READ,
            Permission.METRIC_CREATE,
            Permission.REPORT_READ,
            Permission.REPORT_CREATE,
            Permission.REDTEAM_READ,
            Permission.REDTEAM_CREATE,
            Permission.REDTEAM_EXECUTE,
            Permission.ANALYTICS_READ,
            Permission.DATASET_READ,
            Permission.DATASET_CREATE,
            Permission.DATASET_UPDATE,
            Permission.SETTINGS_READ,
            Permission.APIKEY_CREATE,
            Permission.APIKEY_READ,
        }
    ),
    Role.ANALYST: frozenset(
        {
            Permission.EVALUATION_READ,
            Permission.RUN_READ,
            Permission.METRIC_READ,
            Permission.REPORT_READ,
            Permission.REPORT_CREATE,
            Permission.REPORT_EXPORT,
            Permission.REDTEAM_READ,
            Permission.ANALYTICS_READ,
            Permission.ANALYTICS_EXPORT,
            Permission.DATASET_READ,
            Permission.SETTINGS_READ,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Permission.EVALUATION_READ,
            Permission.RUN_READ,
            Permission.METRIC_READ,
            Permission.REPORT_READ,
            Permission.REDTEAM_READ,
            Permission.ANALYTICS_READ,
            Permission.DATASET_READ,
        }
    ),
}


def get_permissions_for_role(role: Role) -> frozenset[Permission]:
    """Return the set of permissions for a given role."""
    return PERMISSION_MATRIX.get(role, frozenset())


def has_permission(role: Role, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    return permission in PERMISSION_MATRIX.get(role, frozenset())


def has_any_permission(role: Role, permissions: tuple[Permission, ...]) -> bool:
    """Check if a role has any of the specified permissions."""
    role_perms = PERMISSION_MATRIX.get(role, frozenset())
    return bool(role_perms & frozenset(permissions))
