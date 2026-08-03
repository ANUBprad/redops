"""Tests for RBAC roles, permissions, and authorization."""

from app.rbac.permissions import (
    PERMISSION_MATRIX,
    get_permissions_for_role,
    has_any_permission,
    has_permission,
)
from app.rbac.roles import Permission, Role


def test_owner_has_all_permissions() -> None:
    owner_perms = get_permissions_for_role(Role.OWNER)
    for perm in Permission:
        assert perm in owner_perms, f"Owner missing permission: {perm}"


def test_viewer_has_read_only_permissions() -> None:
    viewer_perms = get_permissions_for_role(Role.VIEWER)
    assert Permission.EVALUATION_READ in viewer_perms
    assert Permission.RUN_READ in viewer_perms
    assert Permission.EVALUATION_CREATE not in viewer_perms
    assert Permission.EVALUATION_DELETE not in viewer_perms
    assert Permission.REDTEAM_EXECUTE not in viewer_perms


def test_admin_permissions() -> None:
    admin_perms = get_permissions_for_role(Role.ADMIN)
    assert Permission.EVALUATION_CREATE in admin_perms
    assert Permission.EVALUATION_DELETE in admin_perms
    assert Permission.ORG_INVITE in admin_perms
    assert Permission.ORG_REMOVE_MEMBER in admin_perms
    assert Permission.ORG_MANAGE not in admin_perms


def test_developer_permissions() -> None:
    dev_perms = get_permissions_for_role(Role.DEVELOPER)
    assert Permission.EVALUATION_CREATE in dev_perms
    assert Permission.RUN_CREATE in dev_perms
    assert Permission.REDTEAM_EXECUTE in dev_perms
    assert Permission.ANALYTICS_EXPORT not in dev_perms
    assert Permission.ORG_INVITE not in dev_perms


def test_analyst_permissions() -> None:
    analyst_perms = get_permissions_for_role(Role.ANALYST)
    assert Permission.EVALUATION_READ in analyst_perms
    assert Permission.REPORT_CREATE in analyst_perms
    assert Permission.REPORT_EXPORT in analyst_perms
    assert Permission.ANALYTICS_EXPORT in analyst_perms
    assert Permission.EVALUATION_CREATE not in analyst_perms
    assert Permission.REDTEAM_EXECUTE not in analyst_perms


def test_has_permission() -> None:
    assert has_permission(Role.OWNER, Permission.EVALUATION_CREATE) is True
    assert has_permission(Role.VIEWER, Permission.EVALUATION_CREATE) is False
    assert has_permission(Role.ADMIN, Permission.ORG_INVITE) is True
    assert has_permission(Role.DEVELOPER, Permission.ORG_INVITE) is False


def test_has_any_permission() -> None:
    assert has_any_permission(
        Role.DEVELOPER,
        (Permission.EVALUATION_CREATE, Permission.RUN_CREATE),
    ) is True
    assert has_any_permission(
        Role.VIEWER,
        (Permission.EVALUATION_CREATE, Permission.RUN_CREATE),
    ) is False


def test_permission_matrix_completeness() -> None:
    for role in Role:
        assert role in PERMISSION_MATRIX, f"Role {role} missing from matrix"
    for role, perms in PERMISSION_MATRIX.items():
        for perm in perms:
            assert isinstance(perm, Permission), f"Invalid permission in {role}: {perm}"
