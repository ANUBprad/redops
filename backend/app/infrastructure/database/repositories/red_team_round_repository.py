"""SQLAlchemy repository for durable red-team campaign rounds."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.red_team_round import RedTeamRoundModel


class SqlAlchemyRedTeamRoundRepository:
    """Stores and retrieves durable red-team round checkpoints.

    Instances are cheap and tied to a single session, matching the
    per-activity session pattern used across the Temporal activities.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with a database session."""
        self._session = session

    async def find_all(
        self,
        attack_run_id: str,
    ) -> list[RedTeamRoundModel]:
        """Return all durable rounds for a run, ordered by round number."""
        rows = await self._session.scalars(
            select(RedTeamRoundModel)
            .where(RedTeamRoundModel.attack_run_id == attack_run_id)
            .order_by(RedTeamRoundModel.round_number)
        )
        return list(rows)

    async def upsert(
        self,
        attack_run_id: str,
        round_number: int,
        round_json: dict[str, Any],
    ) -> None:
        """Create or update the durable record for a completed round.

        Converges on the composite primary key: a concurrent retry
        finds the existing row and updates it into a single record
        instead of duplicating it.
        """
        row = await self._session.scalar(
            select(RedTeamRoundModel).where(
                RedTeamRoundModel.attack_run_id == attack_run_id,
                RedTeamRoundModel.round_number == round_number,
            )
        )
        if row is None:
            row = RedTeamRoundModel(
                attack_run_id=attack_run_id,
                round_number=round_number,
            )
            self._session.add(row)
        row.round_json = round_json
