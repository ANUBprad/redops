"""Widen metric_results.item_id to the durable item execution boundary.

item_ids are arbitrary caller-supplied strings (not UUID-only) that must
survive the full execution path. The durable item execution boundary
(item_executions.item_id) already holds String(128); this migration widens
metric_results.item_id from String(36) so the same identifier domain is
representable at both persistence boundaries. Postgres enforces VARCHAR
length on insert; without this widening a 37-128 character id paid the
provider and LLM judges before failing metric persistence.

Revision ID: 024
Revises: 023
Create Date: 2026-09-18
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence


revision: str = "024"
down_revision: str | None = "023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Widen metric_results.item_id 36 -> 128.

    Postgres gets a plain ALTER COLUMN (also the offline --sql OPS path);
    SQLite has no ALTER COLUMN TYPE support, so it rebuilds the table via
    batch_alter_table, copying data and recreating the existing indexes —
    the identity index uq_metric_results_run_item_metric (run_id, item_id,
    metric_name) is preserved.
    """
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("metric_results") as batch_op:
            batch_op.alter_column(
                "item_id",
                existing_type=sa.String(36),
                type_=sa.String(128),
                existing_nullable=False,
            )
        return
    op.alter_column(
        "metric_results",
        "item_id",
        existing_type=sa.String(36),
        type_=sa.String(128),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Revert metric_results.item_id 128 -> 36."""
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("metric_results") as batch_op:
            batch_op.alter_column(
                "item_id",
                existing_type=sa.String(128),
                type_=sa.String(36),
                existing_nullable=False,
            )
        return
    op.alter_column(
        "metric_results",
        "item_id",
        existing_type=sa.String(128),
        type_=sa.String(36),
        existing_nullable=False,
    )
