"""P6-B4: system prompt configuration propagation tests.

Deterministic proof that the configured system_prompt survives the full
production path and is actually present in the provider request built by
TargetExecutor:

    config dict
        -> handlers._dict_to_config
        -> AttackConfiguration.system_prompt
        -> repository _config_to_dict / _dict_to_config round-trip
        -> RedTeamWorkflowInput (as the API start endpoint constructs it)
        -> red_team_campaign_activity / workflow forwarding
        -> AdaptiveCampaign.system_prompt
        -> AdaptiveCampaignEngine -> scenario.system_prompt_override
        -> TargetExecutor -> Message.system(...)
        -> provider.chat(messages, ...)  <- asserted at this boundary

The provider receives the system prompt through the EXISTING message
representation (MessageRole.SYSTEM as the leading message). TargetExecutor,
the mutation rebuild, and the provider mappers already understood this
representation before this phase; the configured value just never reached it.
No new prompt abstraction was added.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.evaluation.judge.prompts import SYSTEM_PROMPT as _JUDGE_ENGINE_SYSTEM_PROMPT
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
from app.providers.models.enums import FinishReason, MessageRole
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry
from app.redteam.application.handlers import _dict_to_config as _api_dict_to_config
from app.redteam.domain.campaign import AdaptiveCampaign, CampaignBudget
from app.redteam.domain.entities import AttackRun
from app.redteam.engine.campaign_engine import AdaptiveCampaignEngine
from app.redteam.engine.semantic_judge import SEMANTIC_JUDGE_SYSTEM_PROMPT
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
CONFIGURED_SYSTEM_PROMPT = "You are a strict evaluator."
# Deliberately distinct from any hard-coded/default prompt so the
# provider-boundary assertion cannot accidentally pass.
DISTINCT_SYSTEM_PROMPT = "D4n80adb0721-You-are-the-honcho-of-twisted-trees."


class _EmptyMetricEngine:
    def resolve_metrics(self, names: Any) -> list[Any]:
        return []

    async def evaluate_batch(self, resolved: Any, metric_input: Any) -> list[Any]:
        return []


def _chat_response(content: str, *, input_tokens: int = 10, output_tokens: int = 5) -> ChatResponse:
    return ChatResponse(
        content=content,
        model="test-model",
        provider="test-provider",
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
        finish_reason=FinishReason.STOP,
    )


class _RecordingProvider:
    """Deterministic fake provider that records every chat request it saw.

    Records the full messages list each call so tests can assert what
    actually reached the provider boundary (role + exact content).
    """

    def __init__(self, provider_name: str, content: str = _JUDGE_JSON) -> None:
        self.provider_name = provider_name
        self._content = content
        self.calls: list[tuple[list[Any], str, Any]] = []

    async def chat(self, messages: Any, *, model: str, options: Any = None) -> ChatResponse:
        self.calls.append((list(messages), model, options))
        return _chat_response(self._content)

    async def health(self) -> bool:
        return True

    def capabilities(self) -> Any:
        return object()

    def target_system_prompts(self) -> list[str]:
        """System-prompt contents seen on TARGET calls (judge calls excluded).

        TargetExecutor always leads with Message.system(...) when a scenario
        override is present; the semantic judge sends its own distinct system
        prompt on separate calls.
        """
        excluded = {SEMANTIC_JUDGE_SYSTEM_PROMPT, _JUDGE_ENGINE_SYSTEM_PROMPT}
        seen: list[str] = []
        for messages, _model, _options in self.calls:
            if messages and messages[0].role == MessageRole.SYSTEM:
                content = messages[0].content
                if content not in excluded:
                    seen.append(content)
        return seen

    def target_call_has_system_message(self) -> bool:
        return bool(self.target_system_prompts())

    def target_calls_without_system_message(self) -> int:
        """Count target calls that led with a user message (no system prompt)."""
        count = 0
        for messages, _model, _options in self.calls:
            if messages and messages[0].role == MessageRole.USER:
                count += 1
        return count


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


def _system_prompt_config_dict(*, system_prompt: str, **extra: Any) -> dict[str, Any]:
    return {
        "target_provider": "test-provider",
        "target_model": "test-model",
        **extra,
        **({"system_prompt": system_prompt} if system_prompt else {}),
    }


def _workflow_input(run_id: str, config: Any, **overrides: Any) -> RedTeamWorkflowInput:
    """Mirrors the API start endpoint's config -> input construction."""
    overrides.setdefault("system_prompt", config.system_prompt)
    return RedTeamWorkflowInput(
        attack_run_id=run_id,
        target_provider=config.target_provider,
        target_model=config.target_model,
        target_temperature=config.temperature,
        target_max_tokens=config.max_tokens,
        mutation_provider=config.mutation_provider,
        mutation_model=config.mutation_model,
        mutation_strategy=config.mutation_strategy,
        attack_categories=tuple(c.value for c in config.categories),
        **overrides,
    )


def _build_engine(registry: ProviderRegistry) -> AdaptiveCampaignEngine:
    return AdaptiveCampaignEngine(
        registry=registry,
        metric_engine=None,
        metric_names=(),
        semantic_judge=None,
        judge_provider=None,
        mutation_provider=None,
        mutation_model="",
        mutation_strategy=None,
        cancelled=None,
    )


def _run(coro: Any) -> Any:
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Config hydration + persistence round-trip
# ---------------------------------------------------------------------------


class TestSystemPromptConfigHydration:
    def test_handlers_dict_to_config_preserves_exact_system_prompt(self) -> None:
        config = _api_dict_to_config(
            _system_prompt_config_dict(system_prompt=CONFIGURED_SYSTEM_PROMPT)
        )
        assert config is not None
        assert config.system_prompt == CONFIGURED_SYSTEM_PROMPT

    def test_repository_round_trip_preserves_exact_system_prompt(self) -> None:
        created = _api_dict_to_config(
            _system_prompt_config_dict(system_prompt=DISTINCT_SYSTEM_PROMPT)
        )
        assert created is not None
        hydrated = _repo_dict_to_config(_config_to_dict(created))
        assert hydrated.system_prompt == DISTINCT_SYSTEM_PROMPT

    def test_omitted_system_prompt_defaults_to_empty(self) -> None:
        config = _api_dict_to_config(
            {"target_provider": "test-provider", "target_model": "test-model"}
        )
        assert config is not None
        assert config.system_prompt == ""


# ---------------------------------------------------------------------------
# Temporal forwarding: workflow input -> activity input preserves system_prompt
# ---------------------------------------------------------------------------


_propagation_captured: list[RedTeamWorkflowInput] = []


@activity.defn(name="red_team_campaign_activity")
async def _system_prompt_propagation_stub(
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


class TestWorkflowSystemPromptForwarding:
    async def test_workflow_forwards_system_prompt_to_activity(
        self, time_skipping_env: WorkflowEnvironment
    ) -> None:
        _propagation_captured.clear()
        wf_input = RedTeamWorkflowInput(
            attack_run_id="system-prompt-forward-test",
            target_provider="test-provider",
            target_model="test-model",
            system_prompt=DISTINCT_SYSTEM_PROMPT,
        )
        async with Worker(
            time_skipping_env.client,
            task_queue="system-prompt-forward-q",
            workflows=[RedTeamWorkflow],
            activities=[_system_prompt_propagation_stub],
        ):
            result = await time_skipping_env.client.execute_workflow(
                RedTeamWorkflow.run,
                wf_input,
                id="system-prompt-forward-wf",
                task_queue="system-prompt-forward-q",
            )

        assert result.status == "completed"
        assert len(_propagation_captured) == 1
        assert _propagation_captured[0].system_prompt == DISTINCT_SYSTEM_PROMPT

    async def test_workflow_omitted_system_prompt_defaults_to_empty(
        self, time_skipping_env: WorkflowEnvironment
    ) -> None:
        _propagation_captured.clear()
        wf_input = RedTeamWorkflowInput(
            attack_run_id="system-prompt-omitted-test",
            target_provider="test-provider",
            target_model="test-model",
        )
        async with Worker(
            time_skipping_env.client,
            task_queue="system-prompt-omitted-q",
            workflows=[RedTeamWorkflow],
            activities=[_system_prompt_propagation_stub],
        ):
            await time_skipping_env.client.execute_workflow(
                RedTeamWorkflow.run,
                wf_input,
                id="system-prompt-omitted-wf",
                task_queue="system-prompt-omitted-q",
            )

        assert _propagation_captured[0].system_prompt == ""


# ---------------------------------------------------------------------------
# Provider boundary: what actually reaches provider.chat()
# ---------------------------------------------------------------------------


def _safe_registry(provider: _RecordingProvider) -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(provider)
    return registry


class TestConfiguredSystemPromptReachesProviderBoundary:
    async def test_configured_system_prompt_arrives_at_provider_boundary_via_activity(
        self,
    ) -> None:
        import app.redteam.temporal.activities as mod

        factory = await _build_factory()
        run = await _create_run(factory)
        provider = _RecordingProvider("test-provider")
        registry = _safe_registry(provider)

        old_registry = mod._provider_registry
        old_metric = mod._metric_engine
        old_session = mod._session_factory
        try:
            configure_redteam_provider_registry(registry)
            configure_redteam_metric_engine(_EmptyMetricEngine())
            configure_redteam_session_factory(factory)

            config = _api_dict_to_config(
                _system_prompt_config_dict(
                    system_prompt=CONFIGURED_SYSTEM_PROMPT,
                    max_rounds=1,
                    max_attacks=100,
                )
            )
            assert config is not None
            result = await red_team_campaign_activity(
                _workflow_input(
                    str(run.id), config, max_rounds=1, max_attacks=100, max_total_tokens=1_000_000
                )
            )
        finally:
            mod._provider_registry = old_registry
            mod._metric_engine = old_metric
            mod._session_factory = old_session

        assert result.status == "budget_exhausted"
        assert provider.calls, "the recording provider received no chat calls"
        assert provider.target_system_prompts() == [CONFIGURED_SYSTEM_PROMPT]

    def test_distinct_system_prompt_reaches_provider_boundary_direct_engine(self) -> None:
        provider = _RecordingProvider("test-provider")
        registry = _safe_registry(provider)
        engine = _build_engine(registry)

        campaign = AdaptiveCampaign.create(
            name="system-prompt-distinct",
            target_provider="test-provider",
            target_model="test-model",
            system_prompt=DISTINCT_SYSTEM_PROMPT,
            budget=CampaignBudget(max_rounds=1, max_attacks=100, max_total_tokens=1_000_000),
        )
        result = _run(engine.run_campaign(campaign))

        assert result.total_rounds == 1
        assert result.state.value == "budget_exhausted"
        assert provider.calls, "the recording provider received no chat calls"
        assert provider.target_system_prompts() == [DISTINCT_SYSTEM_PROMPT]

    def test_system_prompt_survives_mutation_rebuild_at_provider_boundary(self) -> None:
        """Target-only semantics: the system prompt rides on the scenario
        through the mutation rebuild, so every target call (seed + mutated)
        still carries the configured prompt."""
        provider = _RecordingProvider("test-provider")
        registry = _safe_registry(provider)
        engine = _build_engine(registry)

        campaign = AdaptiveCampaign.create(
            name="system-prompt-mutation",
            target_provider="test-provider",
            target_model="test-model",
            system_prompt=CONFIGURED_SYSTEM_PROMPT,
            budget=CampaignBudget(max_rounds=2, max_attacks=100, max_total_tokens=1_000_000),
        )
        result = _run(engine.run_campaign(campaign))

        assert result.total_rounds == 2
        target_prompts = provider.target_system_prompts()
        assert len(target_prompts) == 2
        assert set(target_prompts) == {CONFIGURED_SYSTEM_PROMPT}


class TestOmittedSystemPromptKeepsExistingBehavior:
    def test_omitted_system_prompt_sends_no_system_message(self) -> None:
        provider = _RecordingProvider("test-provider")
        registry = _safe_registry(provider)
        engine = _build_engine(registry)

        campaign = AdaptiveCampaign.create(
            name="system-prompt-omitted",
            target_provider="test-provider",
            target_model="test-model",
            budget=CampaignBudget(max_rounds=1, max_attacks=100, max_total_tokens=1_000_000),
        )
        result = _run(engine.run_campaign(campaign))

        assert result.total_rounds == 1
        # Existing behavior: an omitted system prompt means a plain
        # [user] request — no invented default system message.
        assert provider.target_calls_without_system_message() == 1
        assert provider.target_system_prompts() == []

    async def test_omitted_system_prompt_via_activity_leaves_no_system_message(
        self,
    ) -> None:
        import app.redteam.temporal.activities as mod

        factory = await _build_factory()
        run = await _create_run(factory)
        provider = _RecordingProvider("test-provider")
        registry = _safe_registry(provider)

        old_registry = mod._provider_registry
        old_metric = mod._metric_engine
        old_session = mod._session_factory
        try:
            configure_redteam_provider_registry(registry)
            configure_redteam_metric_engine(_EmptyMetricEngine())
            configure_redteam_session_factory(factory)

            config = _api_dict_to_config(
                {"target_provider": "test-provider", "target_model": "test-model"}
            )
            assert config is not None
            result = await red_team_campaign_activity(
                _workflow_input(str(run.id), config, max_rounds=1, max_attacks=100)
            )
        finally:
            mod._provider_registry = old_registry
            mod._metric_engine = old_metric
            mod._session_factory = old_session

        assert result.status == "budget_exhausted"
        assert provider.calls, "the recording provider received no chat calls"
        assert provider.target_system_prompts() == []
        # No invented default reached the boundary — the target call(s) did
        # not lead with any non-judge system message.
        assert not provider.target_call_has_system_message()


# ---------------------------------------------------------------------------
# Retry / replay: same rehydrated config reproduces the same system prompt
# ---------------------------------------------------------------------------


class TestSystemPromptReplayFidelity:
    async def test_same_hydrated_config_reproduces_identical_system_prompt(self) -> None:
        import app.redteam.temporal.activities as mod

        factory = await _build_factory()
        registry = _safe_registry(_RecordingProvider("test-provider"))

        old_registry = mod._provider_registry
        old_metric = mod._metric_engine
        old_session = mod._session_factory
        try:
            configure_redteam_provider_registry(registry)
            configure_redteam_metric_engine(_EmptyMetricEngine())
            configure_redteam_session_factory(factory)

            config = _api_dict_to_config(
                _system_prompt_config_dict(
                    system_prompt=DISTINCT_SYSTEM_PROMPT,
                    max_rounds=1,
                    max_attacks=100,
                )
            )
            assert config is not None
            hydrated = _repo_dict_to_config(_config_to_dict(config))
            assert hydrated.system_prompt == DISTINCT_SYSTEM_PROMPT

            captured_prompts: list[str] = []

            run1 = await _create_run(factory)
            provider1 = _RecordingProvider("test-provider")
            mod._provider_registry = _safe_registry(provider1)
            await red_team_campaign_activity(
                _workflow_input(str(run1.id), hydrated, max_rounds=1, max_attacks=100)
            )
            captured_prompts.extend(provider1.target_system_prompts())

            run2 = await _create_run(factory)
            provider2 = _RecordingProvider("test-provider")
            mod._provider_registry = _safe_registry(provider2)
            await red_team_campaign_activity(
                _workflow_input(str(run2.id), hydrated, max_rounds=1, max_attacks=100)
            )
            captured_prompts.extend(provider2.target_system_prompts())
        finally:
            mod._provider_registry = old_registry
            mod._metric_engine = old_metric
            mod._session_factory = old_session

        assert captured_prompts == [DISTINCT_SYSTEM_PROMPT, DISTINCT_SYSTEM_PROMPT]
