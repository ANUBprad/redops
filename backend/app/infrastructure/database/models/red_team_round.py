"""SQLAlchemy ORM model for durable red-team campaign rounds."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base


class RedTeamRoundModel(Base):
    """ORM model for the red_team_rounds table.

    Stores the fully executed and evaluated round for one
    ``(attack_run_id, round_number)`` pair. The record is written after
    the target/mutation/judge providers have run and the round has been
    assembled, so a Temporal activity that is re-executed after a crash
    resumes from the first incomplete round instead of re-calling the
    providers for already-completed rounds. The composite primary key
    makes concurrent retries converge to a single row.
    """

    __tablename__ = "red_team_rounds"

    attack_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    round_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
