"""Create red_team_rounds table.

Revision ID: 022
Revises: 021
Create Date: 2026-09-16
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence


revision: str = "022"
down_revision: str | None = "021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "red_team_rounds",
        sa.Column("attack_run_id", sa.String(36), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("round_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("attack_run_id", "round_number"),
    )


def downgrade() -> None:
    op.drop_table("red_team_rounds")
