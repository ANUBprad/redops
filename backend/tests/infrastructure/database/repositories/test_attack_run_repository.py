"""Tests for SqlAlchemyAttackRunRepository campaign-results persistence."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.infrastructure.database.models.attack_run import AttackRunModel
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.repositories.attack_run_repository import (
    SqlAlchemyAttackRunRepository,
)
from app.redteam.domain.entities import AttackRun


async def _build_factory() -> async_sessionmaker[Any]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            ([AttackRunModel.__table__]),
        )
    return async_sessionmaker(engine, expire_on_commit=False)


async def _create_run(factory: async_sessionmaker[Any]) -> AttackRun:
    async with factory() as session:
        repo = SqlAlchemyAttackRunRepository(session)
        run = AttackRun.create()
        await repo.save(run)
        await session.commit()
        return run


class TestPersistCampaignResults:
    async def test_persist_and_retrieve_roundtrip(self) -> None:
        """campaign_results persist and are returned by find_by_id."""
        factory = await _build_factory()
        run = await _create_run(factory)
        payload: dict[str, Any] = {
            "campaign_id": str(run.id),
            "state": "completed",
            "total_rounds": 1,
            "rounds": [
                {
                    "round_id": "round-1",
                    "attack_category": "prompt_injection",
                    "execution": {"attack_prompt": "p", "target_response": "r"},
                    "effectiveness": {
                        "evaluation_source": "semantic_judge",
                        "semantic_verdict": "FAILURE",
                    },
                }
            ],
        }

        async with factory() as session:
            repo = SqlAlchemyAttackRunRepository(session)
            await repo.persist_campaign_results(run.id, payload)
            await session.commit()

        async with factory() as session:
            repo = SqlAlchemyAttackRunRepository(session)
            loaded = await repo.find_by_id(run.id)

        assert loaded is not None
        assert loaded.campaign_results == payload

    async def test_persist_missing_run_is_noop(self) -> None:
        """persist_campaign_results for a nonexistent run is a no-op."""
        from app.kernel.entities.base import UUIDv7

        factory = await _build_factory()
        async with factory() as session:
            repo = SqlAlchemyAttackRunRepository(session)
            await repo.persist_campaign_results(UUIDv7(), {"state": "completed"})
            await session.commit()
