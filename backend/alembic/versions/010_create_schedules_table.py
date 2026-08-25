"""Create schedules table.

Revision ID: 010
Revises: 009
Create Date: 2026-07-30
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence


revision: str = "010_create_schedules"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create schedules table."""
    op.create_table(
        "schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("schedule_type", sa.String(50), nullable=False, index=True),
        sa.Column("cron_expression", sa.String(100), nullable=False),
        sa.Column("task_config", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("organization_id", sa.String(36), nullable=True, index=True),
        sa.Column("project_id", sa.String(36), nullable=True, index=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("retry_policy", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("concurrency", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
            index=True,
        ),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """Drop schedules table."""
    op.drop_table("schedules")
