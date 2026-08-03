"""Create agent_runs table.

Revision ID: 014
Revises: 013
Create Date: 2026-08-03
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence


# revision identifiers
revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the agent_runs table."""
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "agent_definition_id",
            sa.String(36),
            nullable=True,
            index=True,
        ),
        sa.Column("agent_name", sa.String(255), nullable=False),
        sa.Column("workflow_id", sa.String(255), nullable=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("steps_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("steps_completed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("steps_failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("token_input", sa.Integer, nullable=False, server_default="0"),
        sa.Column("token_output", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost", sa.Float, nullable=False, server_default="0"),
        sa.Column(
            "average_latency_ms",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("config", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("metadata", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index(
        "ix_agent_runs_created_at",
        "agent_runs",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop the agent_runs table."""
    op.drop_index("ix_agent_runs_created_at", table_name="agent_runs")
    op.drop_table("agent_runs")
