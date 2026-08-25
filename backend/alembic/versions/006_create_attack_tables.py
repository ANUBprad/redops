"""Create attack_definitions and attack_runs tables.

Revision ID: 006
Revises: 005
Create Date: 2026-07-30
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attack_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("category", sa.String(50), nullable=False, index=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft", index=True),
        sa.Column("template", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("parameters", sa.JSON, nullable=False, server_default="{}"),
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
    )
    op.create_index(
        "ix_attack_definitions_category_severity",
        "attack_definitions",
        ["category", "severity"],
    )
    op.create_index(
        "ix_attack_definitions_name",
        "attack_definitions",
        ["name"],
    )

    op.create_table(
        "attack_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("evaluation_run_id", sa.String(36), nullable=True, index=True),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("attack_definition_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("configuration", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("items_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("items_completed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("items_passed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("items_violated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("items_failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_attack_runs_status", "attack_runs", ["status"])
    op.create_index(
        "ix_attack_runs_evaluation_run",
        "attack_runs",
        ["evaluation_run_id"],
    )


def downgrade() -> None:
    op.drop_table("attack_runs")
    op.drop_table("attack_definitions")
