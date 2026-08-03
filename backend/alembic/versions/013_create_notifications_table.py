"""create notifications table

Revision ID: 013
Revises: 012
Create Date: 2026-08-02
"""

import sqlalchemy as sa

from alembic import op

revision = "013_create_notifications"
down_revision = "012_create_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("notification_id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("channel", sa.String(20), nullable=False, index=True),
        sa.Column("event", sa.String(50), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("metadata", sa.JSON, server_default="{}"),
        sa.Column("status", sa.String(20), server_default="pending", index=True),
        sa.Column("target", sa.Text, server_default=""),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
    )
    op.create_index(
        "ix_notifications_org_event",
        "notifications",
        ["organization_id", "event"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_org_event")
    op.drop_table("notifications")
