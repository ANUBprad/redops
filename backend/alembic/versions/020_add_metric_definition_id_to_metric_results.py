"""Add metric_definition_id FK to metric_results.

Revision ID: 020
Revises: 019
Create Date: 2026-08-26
"""

import sqlalchemy as sa

from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "metric_results",
        sa.Column(
            "metric_definition_id",
            sa.Integer(),
            sa.ForeignKey("metric_definitions.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_metric_results_metric_definition_id",
        "metric_results",
        ["metric_definition_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_metric_results_metric_definition_id", table_name="metric_results")
    op.drop_column("metric_results", "metric_definition_id")
