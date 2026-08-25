"""Create agent_trajectories table.

Revision ID: 016
Revises: 015
Create Date: 2026-08-24
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence


# revision identifiers
revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the agent_trajectories table."""
    op.create_table(
        "agent_trajectories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("agent_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("total_steps", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_llm_calls", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_tool_calls", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_tokens_input", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_tokens_output", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_cost_usd", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("total_duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("final_response", sa.Text(), server_default="", nullable=False),
        sa.Column("conversation_history", sa.JSON(), nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=False),
        sa.Column("llm_calls", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_trajectories_run_id", "agent_trajectories", ["run_id"])
    op.create_index("ix_agent_trajectories_created_at", "agent_trajectories", ["created_at"])


def downgrade() -> None:
    """Drop the agent_trajectories table."""
    op.drop_index("ix_agent_trajectories_created_at", table_name="agent_trajectories")
    op.drop_index("ix_agent_trajectories_run_id", table_name="agent_trajectories")
    op.drop_table("agent_trajectories")
