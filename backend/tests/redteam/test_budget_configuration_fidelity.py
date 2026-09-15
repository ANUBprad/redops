"""P6-B3: campaign budget configuration propagation tests.

Deterministic proof that configured max_rounds / max_cost_usd /
max_duration_seconds survive the full production path:

    API config dict
        -> handlers._dict_to_config
        -> AttackConfiguration
        -> repository _config_to_dict / _dict_to_config round-trip
        -> RedTeamWorkflowInput (as the API start endpoint constructs it)
        -> red_team_campaign_activity / workflow forwarding
        -> AdaptiveCampaignEngine
        -> CampaignBudget -> existing enforcement

The enforcement logic itself predates this phase
(CampaignBudget.is_within_limits / AdaptiveCampaign.can_continue). These
tests prove the configured values reach the existing CampaignBudget and
that the existing enforcement honors them. No new budget logic was added.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
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
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry
from app.redteam.application.handlers import _dict_to_config as _api_dict_to_config
from app.redteam.domain.campaign import AdaptiveCampaign, CampaignBudget
from app.redteam.domain.entities import AttackRun
from app.redteam.engine.campaign_engine import AdaptiveCampaignEngine
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
SAFE_TEXT = "I will not comply with that request."
BUDGET_DEFAULTS = (10, 50.0, 3600)


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
    """Deterministic fake provider that records the tokens/responses it saw."""

    def __init__(self, provider_name: str, content: str) -> None:
        self.provider_name = provider_name
        self._content = content

    async def chat(self, messages: Any, *, model: str, options: Any = None) -> ChatResponse:
        return _chat_response(self._content)

    async def health(self) -> bool:
        return True

    def capabilities(self) -> Any:
        return object()


class _PricedProvider:
    """Fake provider registered under a real pricing-table identity.

    The provider name/model (openai / gpt-4o-mini) resolve through the real
    default cost calculator so target-call accounting flows through the
    genuine pricing path instead of fabricated dollar amounts.
    """

    provider_name = "openai"

    async def chat(self, messages: Any, *, model: str, options: Any = None) -> ChatResponse:
        return _chat_response(_JUDGE_JSON, input_tokens=1000, output_tokens=1000)

    async def health(self) -> bool:
        return True

    def capabilities(self) -> Any:
        return object()


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


def _budget_config_dict(**budget: Any) -> dict[str, Any]:
    return {
        "target_provider": "test-provider",
        "target_model": "test-model",
        **budget,
    }


def _workflow_input(run_id: str, config: Any, **overrides: Any) -> RedTeamWorkflowInput:
    """Mirrors the API start endpoint's config -> input construction."""
    overrides.setdefault("max_rounds", config.max_rounds)
    overrides.setdefault("max_cost_usd", config.max_cost_usd)
    overrides.setdefault("max_duration_seconds", config.max_duration_seconds)
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


def _as_campaign_budget(config: Any) -> CampaignBudget:
    """Replicate the activity's input -> CampaignBudget mapping."""
    return CampaignBudget(
        max_rounds=config.max_rounds,
        max_attacks=100,
        max_total_tokens=1_000_000,
        max_cost_usd=config.max_cost_usd,
        max_duration_seconds=config.max_duration_seconds,
        effectiveness_threshold=0.8,
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


# ---------------------------------------------------------------------------
# Config hydration (fails pre-fix: AttackConfiguration has no budget fields)
# ---------------------------------------------------------------------------


class TestBudgetConfigurationHydration:
    def test_handlers_dict_to_config_hydrates_budget_fields(self) -> None:
        config = _api_dict_to_config(
            _budget_config_dict(max_rounds=2, max_cost_usd=0.001, max_duration_seconds=60)
        )
        assert config is not None
        assert config.max_rounds == 2
        assert config.max_cost_usd == 0.001
        assert config.max_duration_seconds == 60

    def test_repository_round_trip_preserves_budget_fields(self) -> None:
        created = _api_dict_to_config(
            _budget_config_dict(max_rounds=3, max_cost_usd=12.5, max_duration_seconds=600)
        )
        assert created is not None
        hydrated = _repo_dict_to_config(_config_to_dict(created))
        assert hydrated.max_rounds == 3
        assert hydrated.max_cost_usd == 12.5
        assert hydrated.max_duration_seconds == 600

    def test_omitted_budget_fields_preserve_execution_defaults(self) -> None:
        config = _api_dict_to_config(
            {"target_provider": "test-provider", "target_model": "test-model"}
        )
        assert config is not None
        assert (
            config.max_rounds,
            config.max_cost_usd,
            config.max_duration_seconds,
        ) == BUDGET_DEFAULTS


# ---------------------------------------------------------------------------
# Workflow forwarding: workflow input -> activity input preserves budget_*
# ---------------------------------------------------------------------------


_propagation_captured: list[RedTeamWorkflowInput] = []


@activity.defn(name="red_team_campaign_activity")
async def _budget_propagation_stub(
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


class TestWorkflowBudgetForwarding:
    async def test_workflow_forwards_budget_fields_to_activity(
        self, time_skipping_env: WorkflowEnvironment
    ) -> None:
        _propagation_captured.clear()
        wf_input = RedTeamWorkflowInput(
            attack_run_id="budget-forward-test",
            target_provider="test-provider",
            target_model="test-model",
            max_rounds=3,
            max_cost_usd=12.5,
            max_duration_seconds=600,
            max_attacks=100,
        )
        async with Worker(
            time_skipping_env.client,
            task_queue="budget-forward-q",
            workflows=[RedTeamWorkflow],
            activities=[_budget_propagation_stub],
        ):
            result = await time_skipping_env.client.execute_workflow(
                RedTeamWorkflow.run,
                wf_input,
                id="budget-forward-wf",
                task_queue="budget-forward-q",
            )

        assert result.status == "completed"
        assert len(_propagation_captured) == 1
        activity_input = _propagation_captured[0]
        assert activity_input.max_rounds == 3
        assert activity_input.max_cost_usd == 12.5
        assert activity_input.max_duration_seconds == 600

    async def test_workflow_omitted_budget_defaults_propagate_unchanged(
        self, time_skipping_env: WorkflowEnvironment
    ) -> None:
        _propagation_captured.clear()
        wf_input = RedTeamWorkflowInput(
            attack_run_id="budget-omitted-test",
            target_provider="test-provider",
            target_model="test-model",
        )
        async with Worker(
            time_skipping_env.client,
            task_queue="budget-omitted-q",
            workflows=[RedTeamWorkflow],
            activities=[_budget_propagation_stub],
        ):
            await time_skipping_env.client.execute_workflow(
                RedTeamWorkflow.run,
                wf_input,
                id="budget-omitted-wf",
                task_queue="budget-omitted-q",
            )

        activity_input = _propagation_captured[0]
        assert activity_input.max_rounds == 10
        assert activity_input.max_cost_usd == 50.0
        assert activity_input.max_duration_seconds == 3600


# ---------------------------------------------------------------------------
# Enforcement: configured max_rounds by the real activity + engine
# ---------------------------------------------------------------------------


def _safe_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(_RecordingProvider("test-provider", SAFE_TEXT))
    return registry


class TestMaxRoundsEnforcement:
    async def test_configured_max_rounds_stops_campaign_via_activity(self) -> None:
        import app.redteam.temporal.activities as mod

        factory = await _build_factory()
        run = await _create_run(factory)
        registry = _safe_registry()

        old_registry = mod._provider_registry
        old_metric = mod._metric_engine
        old_session = mod._session_factory
        try:
            configure_redteam_provider_registry(registry)
            configure_redteam_metric_engine(_EmptyMetricEngine())
            configure_redteam_session_factory(factory)

            config = _api_dict_to_config(_budget_config_dict(max_rounds=2, max_attacks=100))
            assert config is not None
            result = await red_team_campaign_activity(
                _workflow_input(str(run.id), config, max_attacks=100, max_total_tokens=1_000_000)
            )
        finally:
            mod._provider_registry = old_registry
            mod._metric_engine = old_metric
            mod._session_factory = old_session

        assert result.status == "budget_exhausted"
        assert result.error == ""
        assert result.total_rounds == 2

        async with factory() as session:
            repo = SqlAlchemyAttackRunRepository(session)
            loaded = await repo.find_by_id(run.id)
        assert loaded is not None
        assert loaded.campaign_results is not None
        campaign_json = json.loads(json.dumps(loaded.campaign_results))
        assert campaign_json["state"] == "budget_exhausted"
        assert campaign_json["total_rounds"] == 2
        assert campaign_json["budget_violation_reason"] == "max_rounds"

    def test_configured_max_rounds_binds_engine_loop(self) -> None:
        registry = _safe_registry()
        engine = _build_engine(registry)
        config = _api_dict_to_config(_budget_config_dict(max_rounds=2, max_attacks=100))
        assert config is not None

        campaign = AdaptiveCampaign.create(
            name="budget-rounds-control",
            target_provider=config.target_provider,
            target_model=config.target_model,
            budget=_as_campaign_budget(config),
        )
        result = _run(engine.run_campaign(campaign))

        assert result.state.value == "budget_exhausted"
        assert result.total_rounds == 2
        assert result.budget_violation_reason == "max_rounds"


# ---------------------------------------------------------------------------
# Enforcement: configured max_cost_usd through the real pricing calculator
# ---------------------------------------------------------------------------


class TestMaxCostUsdEnforcement:
    async def test_configured_max_cost_usd_stops_campaign_via_activity(self) -> None:
        import app.redteam.temporal.activities as mod

        factory = await _build_factory()
        run = await _create_run(factory)
        registry = ProviderRegistry()
        registry.register(_PricedProvider())

        old_registry = mod._provider_registry
        old_metric = mod._metric_engine
        old_session = mod._session_factory
        try:
            configure_redteam_provider_registry(registry)
            configure_redteam_metric_engine(_EmptyMetricEngine())
            configure_redteam_session_factory(factory)

            config = _api_dict_to_config(
                {
                    "target_provider": "openai",
                    "target_model": "gpt-4o-mini",
                    "max_rounds": 10,
                    "max_attacks": 100,
                    "max_cost_usd": 0.001,
                }
            )
            assert config is not None
            result = await red_team_campaign_activity(_workflow_input(str(run.id), config))
        finally:
            mod._provider_registry = old_registry
            mod._metric_engine = old_metric
            mod._session_factory = old_session

        # openai/gpt-4o-mini = $0.15 input + $0.60 output per 1M tokens;
        # the fake provider reports 1k/1k per call → $0.00075/call.
        # With a $0.001 budget: round 1 (0.00075 < 0.001), round 2 pushes
        # the total to 0.0015 >= 0.001 → cost budget exhausted.
        assert result.status == "budget_exhausted"
        assert result.total_rounds == 2
        assert result.total_cost_usd == pytest.approx(0.0015)

        async with factory() as session:
            repo = SqlAlchemyAttackRunRepository(session)
            loaded = await repo.find_by_id(run.id)
        assert loaded is not None
        assert loaded.campaign_results is not None
        campaign_json = json.loads(json.dumps(loaded.campaign_results))
        assert campaign_json["budget_violation_reason"] == "max_cost_usd"

    def test_configured_max_cost_usd_binds_engine_loop(self) -> None:
        registry = ProviderRegistry()
        registry.register(_PricedProvider())
        engine = _build_engine(registry)
        config = _api_dict_to_config(
            {
                "target_provider": "openai",
                "target_model": "gpt-4o-mini",
                "max_rounds": 10,
                "max_attacks": 100,
                "max_cost_usd": 0.001,
            }
        )
        assert config is not None

        campaign = AdaptiveCampaign.create(
            name="budget-cost-control",
            target_provider=config.target_provider,
            target_model=config.target_model,
            budget=_as_campaign_budget(config),
        )
        result = _run(engine.run_campaign(campaign))

        assert result.state.value == "budget_exhausted"
        assert result.total_rounds == 2
        assert result.budget_violation_reason == "max_cost_usd"


# ---------------------------------------------------------------------------
# Enforcement: configured max_duration_seconds (time-controlled, no sleeps)
# ---------------------------------------------------------------------------


class TestMaxDurationSecondsEnforcement:
    def test_duration_enforcement_observes_configured_value_with_backdated_start(
        self,
    ) -> None:
        """The REAL elapsed_seconds math (wall-clock subtraction from a past
        started_at) trips exactly when the configured duration is exceeded."""
        config = _api_dict_to_config(_budget_config_dict(max_rounds=10, max_duration_seconds=5))
        assert config is not None

        tight = AdaptiveCampaign.create(
            name="budget-duration-tight",
            target_provider=config.target_provider,
            target_model=config.target_model,
            budget=_as_campaign_budget(config),
        )
        tight._started_at = datetime.now(UTC) - timedelta(seconds=6)
        assert tight.can_continue() is False
        assert tight.check_budget_violation() == "max_duration_seconds"

        relaxed = AdaptiveCampaign.create(
            name="budget-duration-relaxed",
            target_provider=config.target_provider,
            target_model=config.target_model,
            budget=_as_campaign_budget(
                _api_dict_to_config(_budget_config_dict(max_rounds=10, max_duration_seconds=3600))
            ),
        )
        relaxed._started_at = datetime.now(UTC) - timedelta(seconds=6)
        assert relaxed.check_budget_violation() is None
        assert relaxed.can_continue() is True

    def test_engine_loop_honors_configured_duration_budget(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Time-controlled loop: elapsed always exceeds the configured budget,
        so the campaign stops before any round and reports the duration reason.
        With the default 3600s budget the same clock still allows rounds."""
        from app.redteam.domain.campaign import AdaptiveCampaign as Campaign

        monkeypatch.setattr(
            Campaign,
            "elapsed_seconds",
            property(lambda self: 6.0),
        )

        registry = _safe_registry()
        engine = _build_engine(registry)
        config = _api_dict_to_config(_budget_config_dict(max_rounds=10, max_duration_seconds=5))
        assert config is not None

        campaign = AdaptiveCampaign.create(
            name="budget-duration-loop",
            target_provider=config.target_provider,
            target_model=config.target_model,
            budget=_as_campaign_budget(config),
        )
        result = _run(engine.run_campaign(campaign))

        assert result.state.value == "budget_exhausted"
        assert result.total_rounds == 0
        # build_result() skips the reason in the zero-round path (pre-existing
        # artifact); attribute the stop to the duration budget directly.
        assert campaign.check_budget_violation() == "max_duration_seconds"

        relaxed_config = _api_dict_to_config(
            _budget_config_dict(max_rounds=2, max_duration_seconds=3600)
        )
        assert relaxed_config is not None
        campaign2 = AdaptiveCampaign.create(
            name="budget-duration-loop-relaxed",
            target_provider=relaxed_config.target_provider,
            target_model=relaxed_config.target_model,
            budget=_as_campaign_budget(relaxed_config),
        )
        result2 = _run(engine.run_campaign(campaign2))

        assert result2.total_rounds == 2
        # max_rounds=2 is the binding constraint; the duration budget did not
        # intervene even though the elapsed clock exceeded it deterministically.
        assert result2.budget_violation_reason == "max_rounds"


# ---------------------------------------------------------------------------
# Retry/replay: same rehydrated config reproduces identical budget behavior
# ---------------------------------------------------------------------------


class TestBudgetReplayFidelity:
    async def test_same_hydrated_config_reproduces_identical_budget_enforcement(
        self,
    ) -> None:
        import app.redteam.temporal.activities as mod

        factory = await _build_factory()
        registry = _safe_registry()

        old_registry = mod._provider_registry
        old_metric = mod._metric_engine
        old_session = mod._session_factory
        try:
            configure_redteam_provider_registry(registry)
            configure_redteam_metric_engine(_EmptyMetricEngine())
            configure_redteam_session_factory(factory)

            config = _api_dict_to_config(_budget_config_dict(max_rounds=2, max_attacks=100))
            assert config is not None
            hydrated = _repo_dict_to_config(_config_to_dict(config))
            assert hydrated.max_rounds == 2

            run1 = await _create_run(factory)
            result1 = await red_team_campaign_activity(
                _workflow_input(str(run1.id), hydrated, max_attacks=100, max_total_tokens=1_000_000)
            )
            run2 = await _create_run(factory)
            result2 = await red_team_campaign_activity(
                _workflow_input(str(run2.id), hydrated, max_attacks=100, max_total_tokens=1_000_000)
            )
        finally:
            mod._provider_registry = old_registry
            mod._metric_engine = old_metric
            mod._session_factory = old_session

        assert result1.status == "budget_exhausted"
        assert result2.status == "budget_exhausted"
        assert result1.total_rounds == 2
        assert result2.total_rounds == 2
        assert result1.total_rounds == result2.total_rounds


def _run(coro: Any) -> Any:
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
