"""SQLAlchemy ORM model for Metric Definitions.

Stores the registry of all available metrics (built-in and plugin-provided).
Populated at startup from the MetricRegistry.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base


class MetricDefinitionModel(Base):
    """ORM model for the metric_definitions table.

    Each row represents one metric implementation: its metadata,
    version, evaluator type, and plugin origin. The ``metric_results``
    table references this via ``metric_definition_id`` for version
    traceability.
    """

    __tablename__ = "metric_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(50))
    scale: Mapped[str] = mapped_column(String(50))
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    evaluator_type: Mapped[str] = mapped_column(String(50), default="heuristic")
    required_inputs: Mapped[list[str]] = mapped_column(JSON, default=list)
    default_weight: Mapped[float] = mapped_column(default=1.0)
    direction: Mapped[str] = mapped_column(String(50), default="higher_is_better")
    default_threshold: Mapped[float | None] = mapped_column(nullable=True)
    requires_context: Mapped[bool] = mapped_column(Boolean, default=False)
    plugin_module: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_metric_definitions_category", "category"),
        Index("ix_metric_definitions_evaluator_type", "evaluator_type"),
        Index("ix_metric_definitions_is_active", "is_active"),
    )
