"""SQLAlchemy ORM model for Audit Logs."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base


class AuditLogModel(Base):
    """ORM model for audit_logs table. Append-only immutable log."""

    __tablename__ = "audit_logs"

    log_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    user_email: Mapped[str] = mapped_column(String(320), default="")
    action: Mapped[str] = mapped_column(String(50), index=True)
    resource_type: Mapped[str] = mapped_column(String(50), index=True)
    resource_id: Mapped[str] = mapped_column(String(36), default="")
    organization_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index(
            "ix_audit_logs_org_action",
            "organization_id",
            "action",
        ),
        Index(
            "ix_audit_logs_org_resource",
            "organization_id",
            "resource_type",
        ),
    )
