"""Create agent_definitions table.

Revision ID: 004
Revises: 003
Create Date: 2026-07-29
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence


# revision identifiers
revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the agent_definitions table."""
    op.create_table(
        "agent_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("agent_type", sa.String(20), nullable=False, server_default="llm"),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("capabilities", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("config", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("endpoint", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", index=True),
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
            name="uq_agent_project_name",
        ),
    )


def downgrade() -> None:
    """Drop the agent_definitions table."""
    op.drop_table("agent_definitions")
