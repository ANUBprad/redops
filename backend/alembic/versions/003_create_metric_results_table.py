"""Create metric_results table.

Revision ID: 003
Revises: 002
Create Date: 2026-07-29
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence


# revision identifiers
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the metric_results table."""
    op.create_table(
        "metric_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), nullable=False, index=True),
        sa.Column("item_id", sa.String(36), nullable=False, index=True),
        sa.Column("metric_name", sa.String(100), nullable=False, index=True),
        sa.Column("score", sa.Float, nullable=False, server_default="0"),
        sa.Column("normalized_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("raw_output", sa.Text, nullable=False, server_default=""),
        sa.Column("reasoning", sa.Text, nullable=False, server_default=""),
        sa.Column("metadata", sa.JSON, nullable=False, server_default="{}"),
        sa.Column(
            "execution_time_ms",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_metric_results_run_metric",
        "metric_results",
        ["run_id", "metric_name"],
    )
    op.create_index(
        "ix_metric_results_run_item",
        "metric_results",
        ["run_id", "item_id"],
    )


def downgrade() -> None:
    """Drop the metric_results table."""
    op.drop_index("ix_metric_results_run_item", table_name="metric_results")
    op.drop_index("ix_metric_results_run_metric", table_name="metric_results")
    op.drop_table("metric_results")
