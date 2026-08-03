"""Tests for Audit Trail domain entity."""

from app.audit.domain.entities import AuditAction, AuditLog, AuditResourceType


def test_audit_log_create() -> None:
    log = AuditLog.create(
        user_id="user-1",
        user_email="test@example.com",
        action=AuditAction.CREATE.value,
        resource_type=AuditResourceType.EVALUATION.value,
        resource_id="eval-1",
        organization_id="org-1",
        ip_address="127.0.0.1",
    )
    assert log.user_id == "user-1"
    assert log.action == "create"
    assert log.resource_type == "evaluation"
    assert log.resource_id == "eval-1"
    assert log.organization_id == "org-1"
    assert log.ip_address == "127.0.0.1"
    assert log.log_id  # UUID generated


def test_audit_log_with_metadata() -> None:
    log = AuditLog.create(
        user_id="user-1",
        action=AuditAction.UPDATE.value,
        resource_type=AuditResourceType.SETTINGS.value,
        metadata={"key": "value", "count": 42},
    )
    assert log.metadata["key"] == "value"
    assert log.metadata["count"] == 42


def test_audit_log_is_immutable() -> None:
    log = AuditLog.create(
        user_id="user-1",
        action=AuditAction.READ.value,
        resource_type=AuditResourceType.USER.value,
    )
    import pytest

    with pytest.raises(AttributeError):
        log.user_id = "user-2"  # type: ignore[misc]


def test_audit_actions_covered() -> None:
    expected_actions = {
        "create",
        "read",
        "update",
        "delete",
        "login",
        "logout",
        "register",
        "invite",
        "accept_invitation",
        "remove_member",
        "change_role",
        "export",
        "execute",
        "cancel",
        "revoke",
        "rotate",
        "verify",
        "reset_password",
        "schedule",
        "notify",
    }
    actual_actions = {a.value for a in AuditAction}
    assert expected_actions == actual_actions
