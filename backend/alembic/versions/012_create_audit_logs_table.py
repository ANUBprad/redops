"""create audit_logs table

Revision ID: 012
Revises: 011
Create Date: 2026-08-02
"""

import sqlalchemy as sa

from alembic import op

revision = "012_create_audit_logs"
down_revision = "011_create_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("log_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_email", sa.String(320), server_default=""),
        sa.Column("action", sa.String(50), nullable=False, index=True),
        sa.Column("resource_type", sa.String(50), nullable=False, index=True),
        sa.Column("resource_id", sa.String(36), server_default=""),
        sa.Column("organization_id", sa.String(36), nullable=True, index=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("metadata", sa.JSON, server_default="{}"),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column("request_id", sa.String(36), nullable=True),
    )
    op.create_index(
        "ix_audit_logs_org_action",
        "audit_logs",
        ["organization_id", "action"],
    )
    op.create_index(
        "ix_audit_logs_org_resource",
        "audit_logs",
        ["organization_id", "resource_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_org_resource")
    op.drop_index("ix_audit_logs_org_action")
    op.drop_table("audit_logs")
