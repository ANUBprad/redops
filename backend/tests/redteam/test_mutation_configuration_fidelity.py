"""P6-B2: mutation configuration propagation tests.

Deterministic proof that configured mutation_provider/mutation_model/
mutation_strategy survive the full production path:

    API config dict
        -> handlers._dict_to_config
        -> AttackConfiguration
        -> repository _config_to_dict / _dict_to_config round-trip
        -> RedTeamWorkflowInput (as the API start endpoint constructs it)
        -> red_team_campaign_activity / workflow forwarding
        -> AdaptiveCampaignEngine
        -> MutationEngine -> provider.chat(...)

Each propagation test fails under the pre-fix code, where
AttackConfiguration lacked the three fields and handlers/workflow
omitted them entirely.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.infrastructure.database.models.attack_run import AttackRunModel
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.infrastructure.database.repositories.attack_run_repository import (
    SqlAlchemyAttackRunRepository,
    _config_to_dict,
)
from app.infrastructure.database.repositories.attack_run_repository import (
    _dict_to_config as _repo_dict_to_config,
)
from app.providers.models.enums import FinishReason
from app.providers.models.options import ChatOptions
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry
from app.redteam.application.handlers import _dict_to_config as _api_dict_to_config
from app.redteam.domain.entities import AttackRun
from app.redteam.temporal.activities import (
    RedTeamWorkflowInput,
    RedTeamWorkflowResult,
    configure_redteam_metric_engine,
    configure_redteam_provider_registry,
    configure_redteam_session_factory,
    red_team_campaign_activity,
)
from app.redteam.temporal.workflow import RedTeamWorkflow

_JUDGE_JSON = (
    '{"verdict":"FAILURE","score":0.1,"confidence":0.9,'
    '"reasoning":"Refused","evidence":"Cannot help"}'
)
_VARIATIONS = "temporal-variation-a\ntemporal-variation-b"


class _EmptyMetricEngine:
    def resolve_metrics(self, names: Any) -> list[Any]:
        return []

    async def evaluate_batch(self, resolved: Any, metric_input: Any) -> list[Any]:
        return []


def _chat_response(content: str) -> ChatResponse:
    return ChatResponse(
        content=content,
        model="test-model",
        provider="test-provider",
        usage=Usage(input_tokens=10, output_tokens=5),
        finish_reason=FinishReason.STOP,
    )


class _TargetProvider:
    provider_name = "test-provider"

    async def chat(self, messages: Any, *, model: str, options: Any = None) -> ChatResponse:
        return _chat_response(_JUDGE_JSON)

    async def health(self) -> bool:
        return True

    def capabilities(self) -> Any:
        return object()


class _RecordingMutator:
    provider_name = "mutator"

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    async def chat(self, messages: Any, *, model: str, options: Any = None) -> ChatResponse:
        self.calls.append((model, options))
        return _chat_response(_VARIATIONS)

    async def health(self) -> bool:
        return True

    def capabilities(self) -> Any:
        return object()


def _build_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(_TargetProvider())
    registry.register(_RecordingMutator())
    return registry


async def _build_factory() -> async_sessionmaker[Any]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            ([AttackRunModel.__table__, MetricResultModel.__table__]),
        )
    return async_sessionmaker(engine, expire_on_commit=False)


async def _create_run(factory: async_sessionmaker[Any]) -> AttackRun:
    async with factory() as session:
        repo = SqlAlchemyAttackRunRepository(session)
        run = AttackRun.create()
        await repo.save(run)
        await session.commit()
        return run


def _mutation_config_dict() -> dict[str, str]:
    return {
        "target_provider": "test-provider",
        "target_model": "test-model",
        "mutation_provider": "mutator",
        "mutation_model": "mutator-model",
        "mutation_strategy": "prompt_variation",
    }


def _workflow_input(run_id: str, config: Any, **overrides: Any) -> RedTeamWorkflowInput:
    """Mirrors the API start endpoint's config -> input construction."""
    overrides.setdefault("max_rounds", 3)
    overrides.setdefault("max_attacks", 3)
    return RedTeamWorkflowInput(
        attack_run_id=run_id,
        target_provider=config.target_provider,
        target_model=config.target_model,
        target_temperature=config.temperature,
        target_max_tokens=config.max_tokens,
        mutation_provider=config.mutation_provider,
        mutation_model=config.mutation_model,
        mutation_strategy=config.mutation_strategy,
        **overrides,
    )


# ---------------------------------------------------------------------------
# Config hydration (fails pre-fix: AttackConfiguration has no mutation_* fields)
# ---------------------------------------------------------------------------


class TestMutationConfigurationHydration:
    def test_handlers_dict_to_config_hydrates_mutation_fields(self) -> None:
        config = _api_dict_to_config(_mutation_config_dict())
        assert config is not None
        assert config.mutation_provider == "mutator"
        assert config.mutation_model == "mutator-model"
        assert config.mutation_strategy == "prompt_variation"

    def test_repository_round_trip_preserves_mutation_fields(self) -> None:
        created = _api_dict_to_config(_mutation_config_dict())
        assert created is not None
        hydrated = _repo_dict_to_config(_config_to_dict(created))
        assert hydrated.mutation_provider == "mutator"
        assert hydrated.mutation_model == "mutator-model"
        assert hydrated.mutation_strategy == "prompt_variation"

    def test_omitted_mutation_fields_default_to_empty_strings(self) -> None:
        config = _api_dict_to_config(
            {"target_provider": "test-provider", "target_model": "test-model"}
        )
        assert config is not None
        assert config.mutation_provider == ""
        assert config.mutation_model == ""
        assert config.mutation_strategy == ""


# ---------------------------------------------------------------------------
# Provider boundary via the real activity (fails pre-fix at config access)
# ---------------------------------------------------------------------------


class TestConfiguredMutationReachesProviderBoundary:
    async def test_mutation_config_reaches_mutator_and_persists_via_activity(
        self,
    ) -> None:
        import app.redteam.temporal.activities as mod

        factory = await _build_factory()
        run = await _create_run(factory)
        registry = _build_registry()
        recording_mutator: _RecordingMutator = registry.resolve("mutator")

        old_registry = mod._provider_registry
        old_metric = mod._metric_engine
        old_session = mod._session_factory
        try:
            configure_redteam_provider_registry(registry)
            configure_redteam_metric_engine(_EmptyMetricEngine())
            configure_redteam_session_factory(factory)

            config = _api_dict_to_config(_mutation_config_dict())
            assert config is not None

            result = await red_team_campaign_activity(_workflow_input(str(run.id), config))
        finally:
            mod._provider_registry = old_registry
            mod._metric_engine = old_metric
            mod._session_factory = old_session

        assert result.status == "budget_exhausted"
        assert result.error == ""

        assert recording_mutator.calls, "configured mutator was never invoked"
        for model, options in recording_mutator.calls:
            assert model == "mutator-model"
            assert isinstance(options, ChatOptions)

        async with factory() as session:
            repo = SqlAlchemyAttackRunRepository(session)
            loaded = await repo.find_by_id(run.id)
        assert loaded is not None
        assert loaded.campaign_results is not None

        campaign_json = json.loads(json.dumps(loaded.campaign_results))
        llm_rounds = [
            rnd
            for rnd in campaign_json.get("rounds", [])
            if ((rnd.get("attack_scenario") or {}).get("metadata") or {}).get("source")
            == "llm_variation"
        ]
        assert llm_rounds, "no LLM-mutated round persisted in campaign result"

        scenario = llm_rounds[0]["attack_scenario"]
        assert scenario["prompt"] == "temporal-variation-a"
        assert scenario["metadata"]["mutation_strategy"] == "prompt_variation"
        assert "original_prompt" in scenario["metadata"]


# ---------------------------------------------------------------------------
# Retry/replay: the same rehydrated config drives identical mutation behavior
# ---------------------------------------------------------------------------


class TestMutationConfigReplayFidelity:
    async def test_same_hydrated_config_reproduces_identical_mutation_invocations(
        self,
    ) -> None:
        import app.redteam.temporal.activities as mod

        factory = await _build_factory()
        registry = _build_registry()
        recording_mutator: _RecordingMutator = registry.resolve("mutator")

        old_registry = mod._provider_registry
        old_metric = mod._metric_engine
        old_session = mod._session_factory
        try:
            configure_redteam_provider_registry(registry)
            configure_redteam_metric_engine(_EmptyMetricEngine())
            configure_redteam_session_factory(factory)

            config = _api_dict_to_config(_mutation_config_dict())
            assert config is not None
            hydrated = _repo_dict_to_config(_config_to_dict(config))
            assert hydrated.mutation_provider == "mutator"
            assert hydrated.mutation_model == "mutator-model"
            assert hydrated.mutation_strategy == "prompt_variation"

            # Two executions (a retry replays the workflow with the same input).
            run1 = await _create_run(factory)
            result1 = await red_team_campaign_activity(
                _workflow_input(str(run1.id), hydrated, max_rounds=2, max_attacks=2)
            )
            first_calls = list(recording_mutator.calls)

            run2 = await _create_run(factory)
            result2 = await red_team_campaign_activity(
                _workflow_input(str(run2.id), hydrated, max_rounds=2, max_attacks=2)
            )
            second_calls = list(recording_mutator.calls[len(first_calls) :])

            assert result1.status == "budget_exhausted"
            assert result2.status == "budget_exhausted"
            assert first_calls and second_calls

            first_models = [model for model, _ in first_calls]
            second_models = [model for model, _ in second_calls]
            assert first_models == second_models
            for _, options in first_calls + second_calls:
                assert isinstance(options, ChatOptions)
        finally:
            mod._provider_registry = old_registry
            mod._metric_engine = old_metric
            mod._session_factory = old_session


# ---------------------------------------------------------------------------
# Workflow forwarding: workflow input -> activity input preserves mutation_*
# ---------------------------------------------------------------------------


_propagation_captured: list[RedTeamWorkflowInput] = []


@activity.defn(name="red_team_campaign_activity")
async def _mutation_propagation_stub(
    dfn: RedTeamWorkflowInput,
) -> RedTeamWorkflowResult:
    _propagation_captured.append(dfn)
    return RedTeamWorkflowResult(
        attack_run_id=dfn.attack_run_id,
        status="completed",
    )


@pytest.fixture
async def time_skipping_env():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


class TestWorkflowMutationForwarding:
    async def test_workflow_forwards_mutation_fields_to_activity(
        self, time_skipping_env: WorkflowEnvironment
    ) -> None:
        _propagation_captured.clear()
        wf_input = RedTeamWorkflowInput(
            attack_run_id="mutation-forward-test",
            target_provider="test-provider",
            target_model="test-model",
            mutation_provider="mutator",
            mutation_model="mutator-model",
            mutation_strategy="prompt_variation",
            max_rounds=1,
            max_attacks=1,
        )
        async with Worker(
            time_skipping_env.client,
            task_queue="mutation-forward-q",
            workflows=[RedTeamWorkflow],
            activities=[_mutation_propagation_stub],
        ):
            result = await time_skipping_env.client.execute_workflow(
                RedTeamWorkflow.run,
                wf_input,
                id="mutation-forward-wf",
                task_queue="mutation-forward-q",
            )

        assert result.status == "completed"
        assert len(_propagation_captured) == 1
        activity_input = _propagation_captured[0]
        assert activity_input.mutation_provider == "mutator"
        assert activity_input.mutation_model == "mutator-model"
        assert activity_input.mutation_strategy == "prompt_variation"

    async def test_workflow_omitted_mutation_defaults_propagate_as_empty(
        self, time_skipping_env: WorkflowEnvironment
    ) -> None:
        _propagation_captured.clear()
        wf_input = RedTeamWorkflowInput(
            attack_run_id="mutation-omitted-test",
            target_provider="test-provider",
            target_model="test-model",
            max_rounds=1,
            max_attacks=1,
        )
        async with Worker(
            time_skipping_env.client,
            task_queue="mutation-omitted-q",
            workflows=[RedTeamWorkflow],
            activities=[_mutation_propagation_stub],
        ):
            await time_skipping_env.client.execute_workflow(
                RedTeamWorkflow.run,
                wf_input,
                id="mutation-omitted-wf",
                task_queue="mutation-omitted-q",
            )

        activity_input = _propagation_captured[0]
        assert activity_input.mutation_provider == ""
        assert activity_input.mutation_model == ""
        assert activity_input.mutation_strategy == ""
