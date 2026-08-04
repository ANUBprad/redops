"""SQLAlchemy ORM model for Metric Results."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base


class MetricResultModel(Base):
    """ORM model for the metric_results table.

    Stores individual metric evaluation results for each item
    in an evaluation run.
    """

    __tablename__ = "metric_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    item_id: Mapped[str] = mapped_column(String(36), index=True)
    metric_name: Mapped[str] = mapped_column(String(100), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    normalized_score: Mapped[float] = mapped_column(Float, default=0.0)
    raw_output: Mapped[str] = mapped_column(Text, default="")
    reasoning: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
    )
    execution_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index(
            "ix_metric_results_run_metric",
            "run_id",
            "metric_name",
        ),
        Index(
            "ix_metric_results_run_item",
            "run_id",
            "item_id",
        ),
    )
