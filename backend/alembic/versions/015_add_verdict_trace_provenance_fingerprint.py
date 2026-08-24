"""Add verdict, trace_data, provenance, and fingerprint to evaluation_runs.

Revision ID: 015
Revises: 014
Create Date: 2026-08-24
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence


# revision identifiers
revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add verdict, trace_data, provenance, and fingerprint columns."""
    op.add_column(
        "evaluation_runs",
        sa.Column("verdict", sa.String(20), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("trace_data", sa.JSON, nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("provenance", sa.JSON, nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("fingerprint", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    """Remove verdict, trace_data, provenance, and fingerprint columns."""
    op.drop_column("evaluation_runs", "fingerprint")
    op.drop_column("evaluation_runs", "provenance")
    op.drop_column("evaluation_runs", "trace_data")
    op.drop_column("evaluation_runs", "verdict")
