"""Create run_events and run_logs tables.

Revision ID: 005
Revises: 004
Create Date: 2026-07-30
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence


revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "run_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False, index=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("data", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_run_events_run_event_type",
        "run_events",
        ["run_id", "event_type"],
    )
    op.create_index(
        "ix_run_events_occurred_at",
        "run_events",
        ["run_id", "occurred_at"],
    )

    op.create_table(
        "run_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), nullable=False, index=True),
        sa.Column("log_id", sa.String(36), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_run_logs_run_level",
        "run_logs",
        ["run_id", "level"],
    )
    op.create_index(
        "ix_run_logs_run_source",
        "run_logs",
        ["run_id", "source"],
    )
    op.create_index(
        "ix_run_logs_timestamp",
        "run_logs",
        ["run_id", "timestamp"],
    )


def downgrade() -> None:
    op.drop_table("run_logs")
    op.drop_table("run_events")
