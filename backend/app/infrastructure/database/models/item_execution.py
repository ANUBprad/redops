"""SQLAlchemy ORM model for durable per-item executions."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base


class ItemExecutionModel(Base):
    """ORM model for the item_executions table.

    Stores the durable provider execution record for one
    ``(run_id, item_id)`` pair. The record is written after a
    successful provider call and before metric evaluation, so a
    Temporal activity that is re-executed after a crash or timeout
    reuses the recorded provider result instead of re-calling the
    provider. The composite primary key makes concurrent retries
    converge to a single row.
    """

    __tablename__ = "item_executions"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    item_index: Mapped[int] = mapped_column(Integer, default=0)
    provider_name: Mapped[str] = mapped_column(String(100), default="")
    model_id: Mapped[str] = mapped_column(String(100), default="")
    prompt: Mapped[str] = mapped_column(Text, default="")
    response: Mapped[str] = mapped_column(Text, default="")
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    tokens_cached: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    cost_estimated: Mapped[bool] = mapped_column(Boolean, default=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    finish_reason: Mapped[str] = mapped_column(String(32), default="unknown")
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
