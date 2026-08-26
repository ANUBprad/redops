"""SQLAlchemy ORM model for Experiments."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base


class ExperimentModel(Base):
    """ORM model for the experiments table.

    Stores experiment configurations that group related evaluation runs.
    """

    __tablename__ = "experiments"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_experiment_project_name"),
        Index("ix_experiments_project_id_created_at", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    baseline_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("evaluation_runs.id"),
        nullable=True,
    )
    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
