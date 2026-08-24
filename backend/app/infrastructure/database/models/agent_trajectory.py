"""SQLAlchemy ORM model for Agent Trajectories."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base


class AgentTrajectoryModel(Base):
    """ORM model for the agent_trajectories table.

    Stores serialized agent execution trajectories for evaluation
    and analysis. Each trajectory captures the full LLM ↔ tool
    interaction loop for a single agent run.
    """

    __tablename__ = "agent_trajectories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30))
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    total_llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    total_tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    final_response: Mapped[str] = mapped_column(Text, default="")
    conversation_history: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
    )
    tool_calls: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
    )
    llm_calls: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_agent_trajectories_run_id", "run_id"),
        Index("ix_agent_trajectories_created_at", "created_at"),
    )
