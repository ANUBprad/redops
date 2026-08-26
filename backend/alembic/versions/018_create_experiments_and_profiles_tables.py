"""Create experiments and evaluation_profiles tables; add experiment_id FK.

Revision ID: 018
Revises: 017
Create Date: 2026-08-26
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence


# revision identifiers
revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create experiments and evaluation_profiles tables; add experiment_id FK."""
    # Experiments table
    op.create_table(
        "experiments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("hypothesis", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
            index=True,
        ),
        sa.Column(
            "baseline_run_id",
            sa.String(36),
            sa.ForeignKey("evaluation_runs.id"),
            nullable=True,
        ),
        sa.Column("conclusion", sa.Text, nullable=True),
        sa.Column("tags", sa.JSON, nullable=False, server_default="[]"),
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
            "project_id", "name", name="uq_experiment_project_name"
        ),
    )
    op.create_index(
        "ix_experiments_project_id_created_at",
        "experiments",
        ["project_id", "created_at"],
    )

    # Evaluation profiles table
    op.create_table(
        "evaluation_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "scope",
            sa.String(20),
            nullable=False,
            server_default="custom",
        ),
        sa.Column("configuration", sa.JSON, nullable=False, server_default="{}"),
        sa.Column(
            "is_builtin",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
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
            "project_id", "name", name="uq_profile_project_name"
        ),
    )

    # Add experiment_id nullable FK to evaluation_runs
    op.add_column(
        "evaluation_runs",
        sa.Column(
            "experiment_id",
            sa.String(36),
            sa.ForeignKey("experiments.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_evaluation_runs_experiment_id",
        "evaluation_runs",
        ["experiment_id"],
    )


def downgrade() -> None:
    """Remove experiment_id FK; drop evaluation_profiles and experiments tables."""
    op.drop_index("ix_evaluation_runs_experiment_id", table_name="evaluation_runs")
    op.drop_column("evaluation_runs", "experiment_id")
    op.drop_table("evaluation_profiles")
    op.drop_index("ix_experiments_project_id_created_at", table_name="experiments")
    op.drop_table("experiments")
