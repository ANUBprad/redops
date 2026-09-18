"""Enforce metric result identity: reconcile drift and deduplicate.

Adds the metric_results columns already present in the ORM model
(confidence, version, cost_usd) when they are missing — migrations
003/020 left them out so production alembic tables lack them — collapses
duplicate (run_id, item_id, metric_name) rows keeping the newest
MAX(id), and enforces one row per result identity with a unique index.

Revision ID: 023
Revises: 022
Create Date: 2026-09-17
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence


revision: str = "023"
down_revision: str | None = "022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_UNIQUE_INDEX = "uq_metric_results_run_item_metric"


def upgrade() -> None:
    bind = op.get_bind()

    # ponytail: column/index guards rely on inspector presence; the offline
    # (--sql) OPS/CP env code path emits this DDL unguarded, which is fine
    # because it is only ever applied once against a fresh target.
    inspector = sa.inspect(bind)

    existing = {c["name"] for c in inspector.get_columns("metric_results")}
    if "confidence" not in existing:
        op.add_column(
            "metric_results",
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        )
    if "version" not in existing:
        op.add_column(
            "metric_results",
            sa.Column("version", sa.String(20), nullable=False, server_default="1.0.0"),
        )
    if "cost_usd" not in existing:
        op.add_column(
            "metric_results",
            sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        )

    # Collapse duplicate result identities. All duplicate sources (repeated
    # /score calls, retried persistence, orchestration re-runs) rewrite the
    # same logical result, so the newest insert (MAX id) is the survivor.
    op.execute(
        sa.text(
            "DELETE FROM metric_results WHERE id NOT IN "
            "(SELECT MAX(id) FROM metric_results "
            "GROUP BY run_id, item_id, metric_name)"
        )
    )

    index_names = {i["name"] for i in inspector.get_indexes("metric_results")}
    constraint_names = {
        c["name"] for c in inspector.get_unique_constraints("metric_results") if c.get("name")
    }
    if _UNIQUE_INDEX not in index_names and _UNIQUE_INDEX not in constraint_names:
        op.create_index(
            _UNIQUE_INDEX,
            "metric_results",
            ["run_id", "item_id", "metric_name"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index(_UNIQUE_INDEX, table_name="metric_results")
    op.drop_column("metric_results", "cost_usd")
    op.drop_column("metric_results", "version")
    op.drop_column("metric_results", "confidence")
