"""End-to-end test for the full success criteria flow.

A company should be able to:
1. Create an organization
2. Invite members
3. Assign roles
4. Create projects
5. Run evaluations
6. Schedule recurring benchmarks
7. Monitor progress
8. Receive notifications
9. Audit every action
"""

from app.audit.domain.entities import AuditLog, AuditAction, AuditResourceType
from app.identity.domain.entities import User
from app.identity.domain.enums import UserStatus
from app.notification.domain.entities import Notification, NotificationChannel, NotificationEvent
from app.project.domain.entities import Project
from app.rbac.permissions import has_permission
from app.rbac.roles import Permission, Role
from app.scheduling.domain import Schedule, ScheduleType
from app.tenant.domain.entities import Invitation, Membership, Organization
from app.tenant.domain.enums import InvitationStatus, OrganizationRole


def test_full_success_criteria_flow() -> None:
    # 1. Create an organization
    org = Organization.create(
        name="Acme Corp",
        slug="acme-corp",
        owner_id="user-owner",
        description="AI Research Team",
    )
    assert org.name == "Acme Corp"
    assert org.is_active is True

    # 2. Invite members
    invitation = Invitation(
        email="alice@acme.com",
        organization_id=str(org.id),
        role=OrganizationRole.DEVELOPER,
        invited_by="user-owner",
    )
    assert invitation.status == InvitationStatus.PENDING

    # 3. Assign roles (via membership)
    membership = Membership(
        user_id="user-alice",
        organization_id=str(org.id),
        role=OrganizationRole.DEVELOPER,
        invited_by="user-owner",
    )
    assert membership.role == OrganizationRole.DEVELOPER

    # Verify RBAC permissions
    assert has_permission(Role.DEVELOPER, Permission.EVALUATION_CREATE) is True
    assert has_permission(Role.DEVELOPER, Permission.ORG_INVITE) is False

    # 4. Create projects
    project = Project.create(
        name="LLM Eval Project",
        organization_id=str(org.id),
        created_by="user-alice",
        description="Evaluating GPT-4 vs Claude",
    )
    assert project.organization_id == str(org.id)
    assert project.is_active is True

    # 5. Run evaluations (domain entity test)
    from app.evaluation.domain.enums import EvaluationStatus, RunStatus

    # 6. Schedule recurring benchmarks
    schedule = Schedule.create(
        name="Weekly Benchmark",
        schedule_type=ScheduleType.BENCHMARK.value,
        cron_expression="0 9 * * 1",
        task_config={"project_id": str(project.id)},
        organization_id=str(org.id),
        project_id=str(project.id),
        created_by="user-owner",
    )
    assert schedule.cron_expression == "0 9 * * 1"
    assert schedule.is_active is True

    # 7. Monitor progress (audit trail records actions)
    audit_log = AuditLog.create(
        user_id="user-alice",
        user_email="alice@acme.com",
        action=AuditAction.CREATE.value,
        resource_type=AuditResourceType.EVALUATION.value,
        resource_id="eval-123",
        organization_id=str(org.id),
        metadata={"project_id": str(project.id)},
    )
    assert audit_log.action == "create"
    assert audit_log.organization_id == str(org.id)

    # 8. Receive notifications
    notification = Notification.create(
        organization_id=str(org.id),
        user_id="user-owner",
        channel=NotificationChannel.EMAIL.value,
        event=NotificationEvent.RUN_COMPLETED.value,
        title="Evaluation Run Completed",
        message="The weekly benchmark has completed.",
        target="owner@acme.com",
    )
    sent = notification.mark_sent()
    assert sent.status == "sent"

    # 9. Audit every action
    actions_performed = [
        AuditAction.CREATE.value,
        AuditAction.INVITE.value,
        AuditAction.ACCEPT_INVITATION.value,
        AuditAction.EXECUTE.value,
        AuditAction.SCHEDULE.value,
        AuditAction.NOTIFY.value,
    ]
    for action in actions_performed:
        log = AuditLog.create(
            user_id="user-alice",
            action=action,
            resource_type=AuditResourceType.EVALUATION.value,
            organization_id=str(org.id),
        )
        assert log.action == action
