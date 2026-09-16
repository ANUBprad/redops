"""Create item_executions table.

Revision ID: 021
Revises: 020
Create Date: 2026-09-16
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence


revision: str = "021"
down_revision: str | None = "020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "item_executions",
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("item_id", sa.String(128), nullable=False),
        sa.Column("item_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("model_id", sa.String(100), nullable=False, server_default=""),
        sa.Column("prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("response", sa.Text(), nullable=False, server_default=""),
        sa.Column("tokens_input", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_output", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_cached", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cost_estimated", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("finish_reason", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("request_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("run_id", "item_id"),
    )


def downgrade() -> None:
    op.drop_table("item_executions")
