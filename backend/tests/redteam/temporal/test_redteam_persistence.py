"""Tests that the red team campaign activity persists results in production path."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.infrastructure.database.models.attack_run import AttackRunModel
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.repositories.attack_run_repository import (
    SqlAlchemyAttackRunRepository,
)
from app.redteam.domain.campaign import (
    AttackEffectiveness,
    CampaignResult,
    CampaignRound,
    TargetExecution,
)
from app.redteam.domain.campaign_enums import CampaignState
from app.redteam.domain.entities import AttackRun
from app.redteam.domain.enums import AttackCategory
from app.redteam.engine.campaign_engine import AdaptiveCampaignEngine
from app.redteam.temporal.activities import (
    RedTeamWorkflowInput,
    configure_redteam_metric_engine,
    configure_redteam_provider_registry,
    configure_redteam_session_factory,
    red_team_campaign_activity,
)


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


def _campaign_result() -> CampaignResult:
    effectiveness = AttackEffectiveness(
        effectiveness_score=0.9,
        evaluation_source="semantic_judge",
        semantic_verdict="FAILURE",
        semantic_confidence=0.7,
        is_violation=True,
        is_violation_severe=True,
    )
    execution = TargetExecution(
        attack_prompt="inject prompt",
        target_response="response",
        tokens_input=10,
        tokens_output=5,
        total_tokens=15,
        cost_usd=0.001,
    )
    return CampaignResult(
        campaign_id="campaign-1",
        state=CampaignState.COMPLETED,
        total_rounds=1,
        total_attacks=1,
        total_tokens=15,
        total_cost_usd=0.001,
        final_effectiveness=0.9,
        peak_effectiveness=0.9,
        violation_count=1,
        severe_violation_count=1,
        rounds=(
            CampaignRound(
                round_number=1,
                attack_category=AttackCategory.PROMPT_INJECTION,
                mutation_strategy="direct",
                execution=execution,
                effectiveness=effectiveness,
            ),
        ),
    )


async def _fake_run_campaign(self, campaign: Any) -> CampaignResult:
    return _campaign_result()


class TestRedTeamActivityPersistence:
    async def test_completed_campaign_persists_per_round_data(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app.redteam.temporal.activities as mod

        factory = await _build_factory()
        run = await _create_run(factory)

        old_registry = mod._provider_registry
        old_metric = mod._metric_engine
        old_session = mod._session_factory
        try:
            configure_redteam_provider_registry(MagicMock())
            configure_redteam_metric_engine(MagicMock())
            configure_redteam_session_factory(factory)
            monkeypatch.setattr(AdaptiveCampaignEngine, "run_campaign", _fake_run_campaign)

            result = await red_team_campaign_activity(
                RedTeamWorkflowInput(
                    attack_run_id=str(run.id),
                    target_provider="openai",
                    target_model="gpt-4",
                )
            )
        finally:
            mod._provider_registry = old_registry
            mod._metric_engine = old_metric
            mod._session_factory = old_session

        assert result.status == "completed"

        async with factory() as session:
            repo = SqlAlchemyAttackRunRepository(session)
            loaded = await repo.find_by_id(run.id)

        assert loaded is not None
        assert loaded.campaign_results is not None
        assert loaded.campaign_results["state"] == "completed"
        assert loaded.campaign_results["final_effectiveness"] == 0.9
        rounds = loaded.campaign_results["rounds"]
        assert len(rounds) == 1
        assert rounds[0]["execution"]["attack_prompt"] == "inject prompt"
        assert rounds[0]["execution"]["target_response"] == "response"
        assert rounds[0]["effectiveness"]["evaluation_source"] == "semantic_judge"
        assert rounds[0]["effectiveness"]["semantic_verdict"] == "FAILURE"

    async def test_activity_raises_when_no_session_factory(self) -> None:
        import app.redteam.temporal.activities as mod

        old = mod._session_factory
        try:
            mod._session_factory = None
            with pytest.raises(RuntimeError, match="Session factory not configured"):
                await mod._get_session()
        finally:
            mod._session_factory = old
