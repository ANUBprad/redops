"""Create metric_definitions table.

Revision ID: 019
Revises: 018
Create Date: 2026-08-26
"""

import sqlalchemy as sa

from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "metric_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("scale", sa.String(length=50), nullable=False),
        sa.Column("version", sa.String(length=20), server_default="1.0.0"),
        sa.Column("evaluator_type", sa.String(length=50), server_default="heuristic"),
        sa.Column("required_inputs", sa.JSON(), nullable=False),
        sa.Column("default_weight", sa.Float(), server_default="1.0"),
        sa.Column("direction", sa.String(length=50), server_default="higher_is_better"),
        sa.Column("default_threshold", sa.Float(), nullable=True),
        sa.Column("requires_context", sa.Boolean(), server_default="false"),
        sa.Column("plugin_module", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_metric_definitions_name",
        "metric_definitions",
        ["name"],
        unique=True,
    )
    op.create_index(
        "ix_metric_definitions_category",
        "metric_definitions",
        ["category"],
    )
    op.create_index(
        "ix_metric_definitions_evaluator_type",
        "metric_definitions",
        ["evaluator_type"],
    )
    op.create_index(
        "ix_metric_definitions_is_active",
        "metric_definitions",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_table("metric_definitions")
