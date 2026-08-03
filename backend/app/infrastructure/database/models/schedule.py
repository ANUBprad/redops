"""SQLAlchemy ORM model for Schedules."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base


class ScheduleModel(Base):
    """ORM model for schedules table."""

    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    schedule_type: Mapped[str] = mapped_column(String(50), index=True)
    cron_expression: Mapped[str] = mapped_column(String(100))
    task_config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    retry_policy: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    concurrency: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
