"""P6-C3: red-team campaign retry idempotency at the round level.

Proves that ``red_team_campaign_activity`` durably checkpoints each fully
executed round (after target + judge + metric computation) into the
``red_team_rounds`` table, so a re-executed activity (Temporal retry after a
worker crash) resumes from the first incomplete round instead of re-calling
the target/mutation/judge providers for already-completed rounds.

The Temporal worker cannot be reliably killed mid-activity in a unit test,
so a crash after durable completion is modelled by invoking the production
activity twice for the same ``(attack_run_id, ...)`` with a deterministic
crash injected at the finalize boundary on the first attempt — exactly the
sequence Temporal performs when it redelivers an activity attempt. One
workflow-level test exercises the same boundary through a real time-skipping
Temporal environment.

Scenarios:
  A. A normal campaign executes each round once and checkpoints durably.
  B. Retry after completed rounds: no provider re-calls, resume continues
     at the first incomplete round (fails pre-fix).
  C. Crash at an in-flight round's durable checkpoint: completed rounds are
     reused and only the incomplete round is re-executed (honest boundary).
  D. A round whose target execution failed is never checkpointed.
  E. Campaign results of completed rounds are preserved across the retry.
  F. Distinct attack runs never reuse each other's durable rounds.
  G. Metric persistence is keyed by the stable durable round ids.
  H. Redelivery AFTER the run committed COMPLETED reconstructs the result
     from durable rounds without re-calling target/mutation/judge providers
     (P6-C6 boundary-G, fails pre-fix).
  I. A terminal run with no durable rounds refuses to re-execute providers
     and fabricates nothing (P6-C6).
  Legacy. Without the red_team_rounds table the activity behaves as before.
  E2E. Full workflow through a real time-skipping Temporal environment.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

import app.redteam.temporal.activities as mod
from app.infrastructure.database.models.attack_run import AttackRunModel
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.infrastructure.database.models.red_team_round import RedTeamRoundModel
from app.infrastructure.database.repositories.attack_run_repository import (
    SqlAlchemyAttackRunRepository,
)
from app.providers.models.enums import FinishReason
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry
from app.redteam.domain.entities import AttackRun
from app.redteam.domain.enums import AttackStatus
from app.redteam.domain.value_objects import AttackConfiguration
from app.redteam.engine.campaign_engine import _RoundPersistenceError
from app.redteam.temporal.activities import (
    RedTeamWorkflowInput,
    configure_redteam_metric_engine,
    configure_redteam_provider_registry,
    configure_redteam_session_factory,
    red_team_campaign_activity,
)
from app.redteam.temporal.workflow import RedTeamWorkflow

# A compliant non-policy response: keyword scoring stays low, effectiveness <
# threshold, so the loop keeps iterating instead of stopping early.
SAFE_TEXT = "I will not comply with that request."


class _EmptyMetricEngine:
    """No-op metric engine so the campaign loop does not depend on LLM metrics."""

    def resolve_metrics(self, names: Any) -> list[Any]:
        return []

    async def evaluate_batch(self, resolved: Any, metric_input: Any) -> list[Any]:
        return []


class RecordingProvider:
    """Provider that records every chat invocation and replies deterministically."""

    def __init__(self, *, content: str = SAFE_TEXT, provider_name: str = "recording") -> None:
        self.chat_calls = 0
        self.content = content
        self.provider_name = provider_name

    async def chat(self, messages: Any, *, model: str, options: Any = None) -> ChatResponse:
        self.chat_calls += 1
        if self.content is None:
            raise RuntimeError("simulated provider outage")
        return ChatResponse(
            content=self.content,
            model=model,
            provider=self.provider_name,
            usage=Usage(input_tokens=4, output_tokens=2),
            finish_reason=FinishReason.STOP,
        )

    async def health(self) -> bool:
        return True

    def capabilities(self) -> Any:
        return object()


class FailingProvider(RecordingProvider):
    """Provider whose chat invocation always raises."""

    async def chat(self, messages: Any, *, model: str, options: Any = None) -> ChatResponse:
        self.chat_calls += 1
        raise RuntimeError("simulated provider outage")


@pytest.fixture(autouse=True)
def _reset_activity_configuration() -> None:
    """Restore activity module globals after each test."""
    old = (
        mod._session_factory,
        mod._provider_registry,
        mod._metric_engine,
    )
    yield
    (
        mod._session_factory,
        mod._provider_registry,
        mod._metric_engine,
    ) = old


async def _make_database(*tables: Any) -> async_sessionmaker[Any]:
    """Create an in-memory SQLite database with the given tables."""
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, list(tables) or None)
    return async_sessionmaker(engine, expire_on_commit=False)


def _configure(factory: async_sessionmaker[Any], provider: RecordingProvider) -> None:
    """Wire the real activity dependencies, mirroring worker startup."""
    registry = ProviderRegistry()
    registry.register(provider)
    configure_redteam_provider_registry(registry)
    configure_redteam_metric_engine(_EmptyMetricEngine())
    configure_redteam_session_factory(factory)


async def _create_running_run(factory: async_sessionmaker[Any]) -> AttackRun:
    async with factory() as session:
        repo = SqlAlchemyAttackRunRepository(session)
        config = AttackConfiguration(
            target_provider="recording",
            target_model="m",
        )
        run = AttackRun.create(configuration=config)
        run.queue()
        run.start(total_items=2)
        await repo.save(run)
        await session.commit()
        return run


async def _load_run(factory: async_sessionmaker[Any], run_id: Any) -> AttackRun | None:
    async with factory() as session:
        repo = SqlAlchemyAttackRunRepository(session)
        return await repo.find_by_id(run_id)


def _input(
    run_id: str, *, max_rounds: int = 2, target_provider: str = "recording"
) -> RedTeamWorkflowInput:
    return RedTeamWorkflowInput(
        attack_run_id=run_id,
        target_provider=target_provider,
        target_model="m",
        max_rounds=max_rounds,
        max_attacks=max_rounds,
        effectiveness_threshold=0.8,
    )


async def _durable_rounds(
    factory: async_sessionmaker[Any],
    run_id: str,
) -> list[RedTeamRoundModel]:
    async with factory() as session:
        rows = await session.scalars(
            select(RedTeamRoundModel)
            .where(RedTeamRoundModel.attack_run_id == run_id)
            .order_by(RedTeamRoundModel.round_number)
        )
        return list(rows)


async def _metric_rows(
    factory: async_sessionmaker[Any],
    run_id: str,
) -> list[MetricResultModel]:
    async with factory() as session:
        rows = await session.scalars(
            select(MetricResultModel).where(MetricResultModel.run_id == run_id)
        )
        return list(rows)


# ---------------------------------------------------------------------------
# Scenario A — a normal campaign executes each round once and checkpoints it
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_normal_campaign_executes_each_round_once_and_checkpoints() -> None:
    factory = await _make_database(
        AttackRunModel.__table__,
        MetricResultModel.__table__,
        RedTeamRoundModel.__table__,
    )
    run = await _create_running_run(factory)
    provider = RecordingProvider()
    _configure(factory, provider)

    result = await red_team_campaign_activity(_input(str(run.id)))

    assert result.status == "budget_exhausted"
    assert result.total_rounds == 2
    # 1 target call + 1 judge call per round, exactly once each.
    assert provider.chat_calls == 4

    loaded = await _load_run(factory, run.id)
    assert loaded is not None
    assert loaded.status == AttackStatus.COMPLETED

    rows = await _durable_rounds(factory, str(run.id))
    assert [r.round_number for r in rows] == [1, 2]
    assert all(r.round_json["execution"]["target_response"] == SAFE_TEXT for r in rows)
    assert all(r.round_json["effectiveness"]["semantic_metric_result"] is not None for r in rows)

    assert len(await _metric_rows(factory, str(run.id))) == 2


# ---------------------------------------------------------------------------
# Scenario B — retry after completed rounds never re-calls the providers
# Core contract; fails pre-fix (attempt 2 re-executes rounds 1..2).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_after_completed_rounds_does_not_recall_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = await _make_database(
        AttackRunModel.__table__,
        MetricResultModel.__table__,
        RedTeamRoundModel.__table__,
    )
    run = await _create_running_run(factory)
    provider = RecordingProvider()
    _configure(factory, provider)

    async def _crash_finalize(attack_run_id: str, result: Any, cancelled: bool) -> None:
        raise RuntimeError("simulated worker crash after durable rounds")

    async def _noop_fail_run(attack_run_id: str, error_message: str) -> None:
        return None

    real_finalize = mod._finalize_run
    real_fail_run = mod._fail_run
    monkeypatch.setattr(mod, "_finalize_run", _crash_finalize)
    monkeypatch.setattr(mod, "_fail_run", _noop_fail_run)

    first = await red_team_campaign_activity(_input(str(run.id)))

    assert first.status == "failed"
    assert "simulated worker crash" in first.error
    rows_after_first = await _durable_rounds(factory, str(run.id))
    assert [r.round_number for r in rows_after_first] == [1, 2]
    assert provider.chat_calls == 4
    run_after_first = await _load_run(factory, run.id)
    assert run_after_first is not None
    # The simulated worker crash never reached finalization: no campaign JSON
    # and the run is still RUNNING for the retry to resume. The F7 ordering
    # fix runs metric persistence BEFORE finalization, so the already-produced
    # metric rows ARE durable even though finalize crashed.
    assert run_after_first.status == AttackStatus.RUNNING
    assert run_after_first.campaign_results is None
    assert len(await _metric_rows(factory, str(run.id))) == 2

    monkeypatch.setattr(mod, "_finalize_run", real_finalize)
    monkeypatch.setattr(mod, "_fail_run", real_fail_run)

    second = await red_team_campaign_activity(_input(str(run.id)))

    # The retry resumes from the first incomplete round = none remain.
    assert provider.chat_calls == 4
    assert second.total_rounds == 2
    assert second.status == "budget_exhausted"

    done = await _load_run(factory, run.id)
    assert done is not None
    assert done.status == AttackStatus.COMPLETED
    assert len(done.campaign_results["rounds"]) == 2
    assert [r["round_number"] for r in done.campaign_results["rounds"]] == [1, 2]
    rows = await _durable_rounds(factory, str(run.id))
    assert [r.round_number for r in rows] == [1, 2]


# ---------------------------------------------------------------------------
# Scenario E — campaign results for completed rounds are preserved, not discarded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_campaign_result_preserves_completed_rounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = await _make_database(
        AttackRunModel.__table__,
        MetricResultModel.__table__,
        RedTeamRoundModel.__table__,
    )
    run = await _create_running_run(factory)
    provider = RecordingProvider()
    _configure(factory, provider)

    async def _crash_finalize(attack_run_id: str, result: Any, cancelled: bool) -> None:
        raise RuntimeError("simulated worker crash after durable rounds")

    async def _noop_fail_run(attack_run_id: str, error_message: str) -> None:
        return None

    real_finalize = mod._finalize_run
    real_fail_run = mod._fail_run
    monkeypatch.setattr(mod, "_finalize_run", _crash_finalize)
    monkeypatch.setattr(mod, "_fail_run", _noop_fail_run)
    await red_team_campaign_activity(_input(str(run.id)))

    durable_before = await _durable_rounds(factory, str(run.id))
    durable_ids = {r.round_json["round_id"] for r in durable_before}
    durable_responses = {r.round_json["execution"]["target_response"] for r in durable_before}

    monkeypatch.setattr(mod, "_finalize_run", real_finalize)
    monkeypatch.setattr(mod, "_fail_run", real_fail_run)
    await red_team_campaign_activity(_input(str(run.id)))

    done = await _load_run(factory, run.id)
    assert done is not None
    assert done.status == AttackStatus.COMPLETED
    rounds = done.campaign_results["rounds"]
    # The retry's terminal blob carries the SAME rounds that were durably
    # checkpointed before the crash — nothing was re-executed or discarded.
    assert {r["round_id"] for r in rounds} == durable_ids
    assert {r["execution"]["target_response"] for r in rounds} == durable_responses
    assert [r["round_number"] for r in rounds] == [1, 2]


# ---------------------------------------------------------------------------
# Scenario G — metric persistence is keyed by the stable durable round ids
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_metric_rows_reuse_stable_round_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = await _make_database(
        AttackRunModel.__table__,
        MetricResultModel.__table__,
        RedTeamRoundModel.__table__,
    )
    run = await _create_running_run(factory)
    provider = RecordingProvider()
    _configure(factory, provider)

    async def _crash_finalize(attack_run_id: str, result: Any, cancelled: bool) -> None:
        raise RuntimeError("simulated worker crash after durable rounds")

    async def _noop_fail_run(attack_run_id: str, error_message: str) -> None:
        return None

    real_finalize = mod._finalize_run
    real_fail_run = mod._fail_run
    monkeypatch.setattr(mod, "_finalize_run", _crash_finalize)
    monkeypatch.setattr(mod, "_fail_run", _noop_fail_run)
    await red_team_campaign_activity(_input(str(run.id)))

    # Restore the real finalize and re-run: the run completes and persists
    # metric rows keyed by the ORIGINAL durable round ids (no orphans).
    monkeypatch.setattr(mod, "_finalize_run", real_finalize)
    monkeypatch.setattr(mod, "_fail_run", real_fail_run)
    await red_team_campaign_activity(_input(str(run.id)))

    durable = await _durable_rounds(factory, str(run.id))
    durable_ids = {r.round_json["round_id"] for r in durable}

    metric_rows = await _metric_rows(factory, str(run.id))
    assert len(metric_rows) == 2
    assert {m.item_id for m in metric_rows} == durable_ids


# ---------------------------------------------------------------------------
# Scenario C — crash at an in-flight round's checkpoint re-executes only it
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkpoint_failure_resumes_from_incomplete_round(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = await _make_database(
        AttackRunModel.__table__,
        MetricResultModel.__table__,
        RedTeamRoundModel.__table__,
    )
    run = await _create_running_run(factory)
    provider = RecordingProvider()
    _configure(factory, provider)

    real_checkpoint = mod._checkpoint_durable_round

    async def flaky_checkpoint(attack_run_id: str, round_: Any) -> None:
        if round_.round_number == 3:
            raise _RoundPersistenceError("injected checkpoint failure on round 3")
        await real_checkpoint(attack_run_id, round_)

    monkeypatch.setattr(mod, "_checkpoint_durable_round", flaky_checkpoint)

    with pytest.raises(_RoundPersistenceError, match="injected checkpoint failure"):
        await red_team_campaign_activity(_input(str(run.id), max_rounds=3))

    # Rounds 1 and 2 are durably completed; round 3 executed but its
    # checkpoint never committed, so it is incomplete.
    rows = await _durable_rounds(factory, str(run.id))
    assert [r.round_number for r in rows] == [1, 2]
    assert provider.chat_calls == 6
    run_after = await _load_run(factory, run.id)
    assert run_after is not None
    assert run_after.status == AttackStatus.RUNNING

    monkeypatch.setattr(mod, "_checkpoint_durable_round", real_checkpoint)

    second = await red_team_campaign_activity(_input(str(run.id), max_rounds=3))

    assert second.status == "budget_exhausted"
    assert second.total_rounds == 3
    # Rounds 1,2 (2 calls each) once + round 3 (2 calls) again = 8 total.
    assert provider.chat_calls == 8
    done = await _load_run(factory, run.id)
    assert done is not None
    assert done.status == AttackStatus.COMPLETED
    final_rows = await _durable_rounds(factory, str(run.id))
    assert [r.round_number for r in final_rows] == [1, 2, 3]
    assert len(await _metric_rows(factory, str(run.id))) == 3


# ---------------------------------------------------------------------------
# Scenario D — a round whose target execution failed is never checkpointed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_round_is_not_checkpointed() -> None:
    factory = await _make_database(
        AttackRunModel.__table__,
        MetricResultModel.__table__,
        RedTeamRoundModel.__table__,
    )
    run = await _create_running_run(factory)
    provider = FailingProvider()
    _configure(factory, provider)

    result = await red_team_campaign_activity(_input(str(run.id)))

    assert result.total_rounds == 2
    # Target call only per round; the judge short-circuits on empty responses.
    assert provider.chat_calls == 2
    assert await _durable_rounds(factory, str(run.id)) == []

    loaded = await _load_run(factory, run.id)
    assert loaded is not None
    assert loaded.status == AttackStatus.COMPLETED
    rounds = loaded.campaign_results["rounds"]
    assert len(rounds) == 2
    assert all(r["execution"]["error"] for r in rounds)


# ---------------------------------------------------------------------------
# Scenario F — distinct attack runs never reuse each other's durable rounds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_distinct_runs_do_not_reuse_each_other_rounds() -> None:
    factory = await _make_database(
        AttackRunModel.__table__,
        MetricResultModel.__table__,
        RedTeamRoundModel.__table__,
    )
    run_a = await _create_running_run(factory)
    run_b = await _create_running_run(factory)
    provider_a = RecordingProvider()
    provider_b = RecordingProvider(provider_name="recording-b")

    registry = ProviderRegistry()
    registry.register(provider_a)
    registry.register(provider_b)
    configure_redteam_provider_registry(registry)
    configure_redteam_metric_engine(_EmptyMetricEngine())
    configure_redteam_session_factory(factory)

    await red_team_campaign_activity(_input(str(run_a.id)))
    # Run B targets its own provider instance: a run must pay for its own
    # provider work, never reuse another run's checkpoint.
    await red_team_campaign_activity(_input(str(run_b.id), target_provider="recording-b"))

    assert provider_a.chat_calls == 4
    assert provider_b.chat_calls == 4

    rows_a = await _durable_rounds(factory, str(run_a.id))
    rows_b = await _durable_rounds(factory, str(run_b.id))
    assert [r.round_number for r in rows_a] == [1, 2]
    assert [r.round_number for r in rows_b] == [1, 2]
    ids_a = {r.round_json["round_id"] for r in rows_a}
    ids_b = {r.round_json["round_id"] for r in rows_b}
    assert ids_a.isdisjoint(ids_b)


# ---------------------------------------------------------------------------
# Legacy — without the red_team_rounds table the activity behaves as before
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_schema_without_round_table_executes_as_before() -> None:
    factory = await _make_database(
        AttackRunModel.__table__,
        MetricResultModel.__table__,
    )
    run = await _create_running_run(factory)
    provider = RecordingProvider()
    _configure(factory, provider)

    result = await red_team_campaign_activity(_input(str(run.id)))

    assert result.status == "budget_exhausted"
    assert result.total_rounds == 2
    assert provider.chat_calls == 4
    loaded = await _load_run(factory, run.id)
    assert loaded is not None
    assert loaded.status == AttackStatus.COMPLETED
    assert len(await _metric_rows(factory, str(run.id))) == 2


# ---------------------------------------------------------------------------
# Scenario B/E2E — real Temporal workflow with the durable schema active
# ---------------------------------------------------------------------------


@pytest.fixture
async def time_skipping_env():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


@pytest.mark.asyncio
async def test_workflow_checkpoints_rounds_with_durable_schema(time_skipping_env) -> None:
    factory = await _make_database(
        AttackRunModel.__table__,
        MetricResultModel.__table__,
        RedTeamRoundModel.__table__,
    )
    run = await _create_running_run(factory)
    provider = RecordingProvider()
    registry = ProviderRegistry()
    registry.register(provider)

    old_registry = mod._provider_registry
    old_metric = mod._metric_engine
    old_session = mod._session_factory
    try:
        configure_redteam_provider_registry(registry)
        configure_redteam_metric_engine(_EmptyMetricEngine())
        configure_redteam_session_factory(factory)

        async with Worker(
            time_skipping_env.client,
            task_queue="red-team-idempotency",
            workflows=[RedTeamWorkflow],
            activities=[red_team_campaign_activity],
        ):
            result = await time_skipping_env.client.execute_workflow(
                RedTeamWorkflow.run,
                _input(str(run.id)),
                id=f"red-team-idem-{run.id}",
                task_queue="red-team-idempotency",
            )
    finally:
        mod._provider_registry = old_registry
        mod._metric_engine = old_metric
        mod._session_factory = old_session

    assert result.status == "budget_exhausted"
    assert result.total_rounds == 2
    assert provider.chat_calls == 4

    done = await _load_run(factory, run.id)
    assert done is not None
    assert done.status == AttackStatus.COMPLETED
    rows = await _durable_rounds(factory, str(run.id))
    assert [r.round_number for r in rows] == [1, 2]
    assert len(await _metric_rows(factory, str(run.id))) == 2


# ---------------------------------------------------------------------------
# Scenario H — P6-C6 boundary-G: redelivery AFTER finalize committed
# COMPLETED reconstructs the result from durable rounds without re-calling
# the target/mutation/judge providers. Fails pre-fix.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_completed_redelivery_does_not_recall_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = await _make_database(
        AttackRunModel.__table__,
        MetricResultModel.__table__,
        RedTeamRoundModel.__table__,
    )
    run = await _create_running_run(factory)
    provider = RecordingProvider()
    mutation_provider = RecordingProvider(provider_name="mutation-llm")

    registry = ProviderRegistry()
    registry.register(provider)
    registry.register(mutation_provider)
    configure_redteam_provider_registry(registry)
    configure_redteam_metric_engine(_EmptyMetricEngine())
    configure_redteam_session_factory(factory)

    def _input_with_mutation() -> RedTeamWorkflowInput:
        return RedTeamWorkflowInput(
            attack_run_id=str(run.id),
            target_provider="recording",
            target_model="m",
            mutation_provider="mutation-llm",
            mutation_model="m",
            mutation_strategy="prompt_variation",
            max_rounds=2,
            max_attacks=2,
            effectiveness_threshold=0.8,
        )

    real_finalize = mod._finalize_run

    async def _crash_after_finalize(attack_run_id: str, result: Any, cancelled: bool) -> None:
        await real_finalize(attack_run_id, result, cancelled)
        raise RuntimeError("simulated crash after COMPLETED run committed, before activity ack")

    async def _noop_fail_run(attack_run_id: str, error_message: str) -> None:
        return None

    monkeypatch.setattr(mod, "_finalize_run", _crash_after_finalize)
    monkeypatch.setattr(mod, "_fail_run", _noop_fail_run)

    first = await red_team_campaign_activity(_input_with_mutation())

    assert first.status == "failed"
    assert "simulated crash after COMPLETED" in first.error
    # Every provider call happened exactly once BEFORE the crash: 2 target +
    # 2 judge calls on the target provider, 1 mutation call on round-2.
    assert provider.chat_calls == 4
    assert mutation_provider.chat_calls == 1

    run_after_first = await _load_run(factory, run.id)
    assert run_after_first is not None
    # The crash happened AFTER finalize committed, so the durable run is
    # COMPLETED: the redelivery must NOT re-execute the campaign.
    assert run_after_first.status == AttackStatus.COMPLETED
    rows_after_first = await _durable_rounds(factory, str(run.id))
    assert [r.round_number for r in rows_after_first] == [1, 2]
    assert len(await _metric_rows(factory, str(run.id))) == 2

    monkeypatch.setattr(mod, "_finalize_run", real_finalize)
    monkeypatch.setattr(mod, "_fail_run", mod._fail_run)

    second = await red_team_campaign_activity(_input_with_mutation())

    # Boundary-G closed: the redelivery reconstructed the result from the
    # durable rounds. Target, judge AND mutation providers were not re-called.
    assert provider.chat_calls == 4
    assert mutation_provider.chat_calls == 1
    assert second.status == "completed"
    assert second.total_rounds == 2

    done = await _load_run(factory, run.id)
    assert done is not None
    assert done.status == AttackStatus.COMPLETED
    assert len(done.campaign_results["rounds"]) == 2
    assert [r["round_number"] for r in done.campaign_results["rounds"]] == [1, 2]
    final_rows = await _durable_rounds(factory, str(run.id))
    assert [r.round_number for r in final_rows] == [1, 2]
    assert len(await _metric_rows(factory, str(run.id))) == 2


# ---------------------------------------------------------------------------
# Scenario I — P6-C6: a terminal run with NO durable rounds refuses to
# re-execute providers and fabricates no result. Fails pre-fix.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_terminal_run_without_durable_rounds_does_not_fabricate_execution() -> None:
    factory = await _make_database(
        AttackRunModel.__table__,
        MetricResultModel.__table__,
        RedTeamRoundModel.__table__,
    )
    async with factory() as session:
        repo = SqlAlchemyAttackRunRepository(session)
        config = AttackConfiguration(
            target_provider="recording",
            target_model="m",
        )
        run = AttackRun.create(configuration=config)
        run.queue()
        run.start(total_items=2)
        run.cancel()
        await repo.save(run)
        await session.commit()

    provider = RecordingProvider()
    _configure(factory, provider)

    result = await red_team_campaign_activity(_input(str(run.id)))

    # The truthful terminal outcome is reported; no provider call is made
    # and no round/cost data is invented.
    assert result.status == "cancelled"
    assert result.total_rounds == 0
    assert "refusing to re-execute provider calls" in result.error
    assert provider.chat_calls == 0

    loaded = await _load_run(factory, run.id)
    assert loaded is not None
    assert loaded.status == AttackStatus.CANCELLED
    assert await _durable_rounds(factory, str(run.id)) == []
    assert await _metric_rows(factory, str(run.id)) == []
