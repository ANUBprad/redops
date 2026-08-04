"""Create evaluation_runs table.

Revision ID: 002
Revises: 001
Create Date: 2026-07-29
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence


# revision identifiers
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the evaluation_runs table."""
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "evaluation_id",
            sa.String(36),
            sa.ForeignKey("evaluations.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("evaluation_name", sa.String(255), nullable=False),
        sa.Column("workflow_id", sa.String(255), nullable=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("items_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("items_completed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("items_failed", sa.Integer, nullable=False, server_default="0"),
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
        sa.Column("profile", sa.JSON, nullable=False, server_default="{}"),
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
        "ix_evaluation_runs_created_at",
        "evaluation_runs",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop the evaluation_runs table."""
    op.drop_index("ix_evaluation_runs_created_at", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
