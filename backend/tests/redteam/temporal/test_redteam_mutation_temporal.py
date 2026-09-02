"""Temporal integration test: the real red-team activity reaches the LLM mutator.

Runs ``red_team_campaign_activity`` with its real dependency wiring
(provider registry, metric engine, session factory) and a deterministic fake
mutation provider. Proves the *production orchestration path* —

API/configuration → RedTeamWorkflowInput → activity → AdaptiveCampaignEngine
→ MutationEngine → LLM mutator → TargetExecutor → persisted CampaignResult —

reaches the LLM mutator and persists the mutated prompt.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.infrastructure.database.models.attack_run import AttackRunModel
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.infrastructure.database.repositories.attack_run_repository import (
    SqlAlchemyAttackRunRepository,
)
from app.providers.models.enums import FinishReason
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry
from app.redteam.domain.entities import AttackRun
from app.redteam.temporal.activities import (
    RedTeamWorkflowInput,
    configure_redteam_metric_engine,
    configure_redteam_provider_registry,
    configure_redteam_session_factory,
    red_team_campaign_activity,
)

_JUDGE_JSON = (
    '{"verdict":"FAILURE","score":0.1,"confidence":0.9,'
    '"reasoning":"Refused","evidence":"Cannot help"}'
)
_VARIATIONS = "temporal-variation-a\ntemporal-variation-b"


class _EmptyMetricEngine:
    """Minimal functional metric engine that computes no scores.

    The production activity configures the real MetricEngine; under the unit
    harness we supply this no-op stand-in so the campaign loop runs to
    completion instead of depending on Live LLM-backed metrics. Returning an
    empty resolution list makes the engine skip metric scoring, which is
    exactly what happens when ``metric_engine=None`` in the existing campaign
    tests — keeping this test focused on the mutation wiring, not metrics.
    """

    def resolve_metrics(self, names):
        return []

    async def evaluate_batch(self, resolved, metric_input):
        return []


def _chat_response(content: str) -> ChatResponse:
    return ChatResponse(
        content=content,
        model="test-model",
        provider="test-provider",
        usage=Usage(input_tokens=10, output_tokens=5),
        finish_reason=FinishReason.STOP,
    )


def _build_registry() -> ProviderRegistry:
    """A registry with a JSON-verdict target provider and an LLM mutator."""

    class _TargetProvider:
        provider_name = "test-provider"

        async def chat(self, messages, *, model, options=None) -> ChatResponse:
            return _chat_response(_JUDGE_JSON)

        async def health(self) -> bool:
            return True

        def capabilities(self):
            return object()

    class _MutatorProvider:
        provider_name = "mutator"

        async def chat(self, messages, *, model, options=None) -> ChatResponse:
            return _chat_response(_VARIATIONS)

        async def health(self) -> bool:
            return True

        def capabilities(self):
            return object()

    registry = ProviderRegistry()
    registry.register(_TargetProvider())
    registry.register(_MutatorProvider())
    return registry


async def _build_factory() -> async_sessionmaker[Any]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            (
                [
                    AttackRunModel.__table__,
                    MetricResultModel.__table__,
                ]
            ),
        )
    return async_sessionmaker(engine, expire_on_commit=False)


async def _create_run(factory: async_sessionmaker[Any]) -> AttackRun:
    async with factory() as session:
        repo = SqlAlchemyAttackRunRepository(session)
        run = AttackRun.create()
        await repo.save(run)
        await session.commit()
        return run


def _find_llm_mutation_rounds(campaign_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Rounds whose scenario provenance is an LLM variation."""
    rounds: list[dict[str, Any]] = []
    for rnd in campaign_json.get("rounds", []):
        metadata = (rnd.get("attack_scenario") or {}).get("metadata") or {}
        if metadata.get("source") == "llm_variation":
            rounds.append(rnd)
    return rounds


class TestRedTeamActivityLLMMutation:
    async def test_activity_reaches_llm_mutator_and_persists_mutation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app.redteam.temporal.activities as mod

        factory = await _build_factory()
        run = await _create_run(factory)

        old_registry = mod._provider_registry
        old_metric = mod._metric_engine
        old_session = mod._session_factory
        try:
            configure_redteam_provider_registry(_build_registry())
            configure_redteam_metric_engine(_EmptyMetricEngine())
            configure_redteam_session_factory(factory)

            result = await red_team_campaign_activity(
                RedTeamWorkflowInput(
                    attack_run_id=str(run.id),
                    target_provider="test-provider",
                    target_model="test-model",
                    mutation_provider="mutator",
                    mutation_model="mutator-model",
                    mutation_strategy="prompt_variation",
                    max_rounds=3,
                    max_attacks=3,
                )
            )
        finally:
            mod._provider_registry = old_registry
            mod._metric_engine = old_metric
            mod._session_factory = old_session

        # budget_exhausted is the normal terminal state after hitting max_rounds.
        assert result.status == "budget_exhausted"
        assert result.error == ""

        async with factory() as session:
            repo = SqlAlchemyAttackRunRepository(session)
            loaded = await repo.find_by_id(run.id)

        assert loaded is not None
        assert loaded.campaign_results is not None

        campaign_json = json.loads(json.dumps(loaded.campaign_results))

        llm_rounds = _find_llm_mutation_rounds(campaign_json)
        assert llm_rounds, "no LLM-mutated round persisted in campaign result"

        # The mutated prompt that was sent to the target is persisted.
        mutated_round = llm_rounds[0]
        scenario = mutated_round["attack_scenario"]
        execution = mutated_round["execution"]
        assert scenario["prompt"] == "temporal-variation-a"
        assert execution["attack_prompt"] == "temporal-variation-a"
        assert scenario["metadata"]["source"] == "llm_variation"
        assert scenario["metadata"]["mutation_strategy"] == "prompt_variation"
        assert "original_prompt" in scenario["metadata"]
