"""Add campaign_results column to attack_runs.

Revision ID: 017
Revises: 016
Create Date: 2026-08-25
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence


# revision identifiers
revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add campaign_results JSON column to attack_runs."""
    op.add_column(
        "attack_runs",
        sa.Column("campaign_results", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove campaign_results column from attack_runs."""
    op.drop_column("attack_runs", "campaign_results")
