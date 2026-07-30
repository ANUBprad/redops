"""SQLAlchemy ORM model for Agent definitions."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base


class AgentDefinitionModel(Base):
    """ORM model for the agent_definitions table.

    Stores agent definitions with all configuration fields.
    Value objects are decomposed into their primitive representations.
    """

    __tablename__ = "agent_definitions"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_agent_project_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_type: Mapped[str] = mapped_column(String(20), default="llm")
    model: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(100))
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    endpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
