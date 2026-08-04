"""create projects table

Revision ID: 011
Revises: 010
Create Date: 2026-08-02
"""

import sqlalchemy as sa

from alembic import op

revision = "011_create_projects"
down_revision = "010_create_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("version", sa.Integer, default=1),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "name",
            name="uq_project_org_name",
        ),
    )


def downgrade() -> None:
    op.drop_table("projects")
