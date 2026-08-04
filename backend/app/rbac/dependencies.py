"""FastAPI dependencies for RBAC authorization."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException

from app.core.dependencies import CurrentUser, get_current_user
from app.rbac.permissions import Permission, has_permission
from app.rbac.roles import Role


def get_current_user_role(current_user: CurrentUser = Depends(get_current_user)) -> Role:
    """Extract the user's role from JWT claims. Defaults to VIEWER."""
    roles = current_user.roles
    if not roles:
        return Role.VIEWER
    # Map the first role string to the Role enum
    for r in roles:
        try:
            return Role(r)
        except ValueError:
            continue
    return Role.VIEWER


def require_permission(permission: Permission) -> Callable[..., Any]:
    """Dependency factory that checks if the current user has a specific permission."""

    async def _check_permission(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        role = Role.VIEWER
        for r in current_user.roles:
            try:
                role = Role(r)
                break
            except ValueError:
                continue
        if not has_permission(role, permission):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {permission.value}",
            )
        return current_user

    return _check_permission


def require_role(*allowed_roles: Role) -> Callable[..., Any]:
    """Dependency factory that checks if the current user has one of the allowed roles."""

    async def _check_role(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        user_role = Role.VIEWER
        for r in current_user.roles:
            try:
                user_role = Role(r)
                break
            except ValueError:
                continue
        if user_role not in allowed_roles:
            role_names = ", ".join(r.value for r in allowed_roles)
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient role. Required: {role_names}",
            )
        return current_user

    return _check_role


def require_owner_or_admin() -> Callable[..., Any]:
    """Shortcut: require Owner or Admin role."""
    return require_role(Role.OWNER, Role.ADMIN)
