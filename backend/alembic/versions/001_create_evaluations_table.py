"""Create evaluations table.

Revision ID: 001
Revises:
Create Date: 2026-07-29
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence


# revision identifiers
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the evaluations table."""
    op.create_table(
        "evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False, index=True),
        sa.Column("dataset_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("metrics", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("tags", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("configuration", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft", index=True),
        sa.Column("created_by", sa.String(100), nullable=True),
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
        sa.UniqueConstraint(
            "project_id",
            "name",
            name="uq_evaluation_project_name",
        ),
    )


def downgrade() -> None:
    """Drop the evaluations table."""
    op.drop_table("evaluations")
