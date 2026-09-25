"""P6-C2: general evaluation item execution idempotency.

Proves that ``execute_item_activity`` durably records a successful
provider execution before metric evaluation, so a re-executed activity
(retry after crash, timeout, or metric failure) reuses the recorded
provider result instead of re-calling the provider — for general
evaluation items whose ids are plain strings or fallback indexes.

The Temporal worker cannot be reliably killed mid-activity in a unit
test, so activity re-execution after a crash is modelled by invoking
the production activity twice for the same ``(run_id, item_id)`` —
exactly the sequence Temporal performs when it redelivers an activity
attempt. One workflow-level test exercises the same boundary through a
real time-skipping Temporal environment.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.evaluation.application.run_commands import CreateEvaluationRunCommand
from app.evaluation.application.run_handlers import CreateEvaluationRunHandler
from app.evaluation.metrics.domain import (
    Metric,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.metrics.implementations import ALL_METRICS
from app.evaluation.temporal import activities as activities_mod
from app.evaluation.temporal.activities import (
    ExecuteItemInput,
    configure_cost_calculator,
    configure_metric_engine,
    configure_provider_registry,
    configure_session_factory,
)
from app.evaluation.temporal.workflow import EvaluationRunWorkflow
from app.evaluation.temporal.workflow import (
    EvaluationRunWorkflowInput as WorkflowInput,
)
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel
from app.infrastructure.database.models.item_execution import ItemExecutionModel
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.infrastructure.database.repositories.evaluation_run_repository import (
    SqlAlchemyEvaluationRunRepository,
)
from app.providers.cost.defaults import build_default_cost_calculator
from app.providers.models.enums import FinishReason
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry

RUN_ID = "run-durable"
ITEM_ID = "item-1"
ITEM_PROMPT = "What is the capital of France?"
ITEM_ANSWER = '{"answer": "Paris"}'


class RecordingChatProvider:
    """Provider that records every chat invocation and replies deterministically."""

    provider_name = "recording"

    def __init__(self) -> None:
        self.calls = 0
        self.last_model: str | None = None

    async def chat(
        self,
        messages: list[Any],
        model: str,
        options: Any = None,
    ) -> ChatResponse:
        self.calls += 1
        self.last_model = model
        return ChatResponse(
            content=ITEM_ANSWER,
            model=model,
            provider=self.provider_name,
            usage=Usage(input_tokens=7, output_tokens=3, total_tokens=10),
            finish_reason=FinishReason.STOP,
        )


class FailingChatProvider(RecordingChatProvider):
    """Provider whose chat invocation always raises."""

    async def chat(
        self,
        messages: list[Any],
        model: str,
        options: Any = None,
    ) -> ChatResponse:
        self.calls += 1
        raise RuntimeError("simulated provider outage")


class CountingMetric(Metric):
    """Metric that records how many times it evaluated."""

    def __init__(self) -> None:
        self.calls = 0

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="counting",
            display_name="Counting",
            description="Counts evaluations deterministically",
            category=MetricCategory.QUALITY,
            scale=MetricScale.BINARY,
            version="1.0.0",
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        self.calls += 1
        return MetricResult(
            metric_name="counting",
            score=0.42,
            normalized_score=0.42,
            version="1.0.0",
        )


def _item_input(
    run_id: str,
    item_index: int,
    item_id: str,
    *,
    metric_names: tuple[str, ...] = (),
) -> ExecuteItemInput:
    """Build an ExecuteItemInput with real item fields."""
    return ExecuteItemInput(
        run_id=run_id,
        item_index=item_index,
        provider_name="recording",
        model_id="gpt-4o",
        metric_names=metric_names,
        prompt=ITEM_PROMPT,
        item_id=item_id,
    )


@pytest.fixture(autouse=True)
def _reset_activity_configuration() -> None:
    """Restore activity module globals after each test."""
    old = (
        activities_mod._session_factory,
        activities_mod._provider_registry,
        activities_mod._metric_engine,
        activities_mod._cost_calculator,
    )
    yield
    (
        activities_mod._session_factory,
        activities_mod._provider_registry,
        activities_mod._metric_engine,
        activities_mod._cost_calculator,
    ) = old


def _configure_pipeline(
    factory: async_sessionmaker[Any],
    registry: ProviderRegistry,
    metric_engine: MetricEngine | None = None,
) -> None:
    """Wire the real activity dependencies, mirroring worker startup."""
    configure_session_factory(factory)
    configure_provider_registry(registry)
    if metric_engine is not None:
        configure_metric_engine(metric_engine)
    configure_cost_calculator(build_default_cost_calculator())


async def _make_database(*tables: Any) -> async_sessionmaker[Any]:
    """Create an in-memory SQLite database with the given tables.

    The explicit table list mirrors the existing integration suite and
    avoids pulling in tables (e.g. run_events/JSONB) that sqlite cannot
    render. FK-referenced tables (metric_definitions) are created
    automatically by SQLAlchemy when listed tables depend on them.
    """
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, list(tables) or None)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _durable_row(
    factory: async_sessionmaker[Any],
    run_id: str,
    item_id: str,
) -> ItemExecutionModel | None:
    """Load the durable execution row for a (run_id, item_id)."""
    async with factory() as session:
        return await session.scalar(
            select(ItemExecutionModel).where(
                ItemExecutionModel.run_id == run_id,
                ItemExecutionModel.item_id == item_id,
            )
        )


async def _durable_rows_for_run(
    factory: async_sessionmaker[Any],
    run_id: str,
) -> list[ItemExecutionModel]:
    """Load all durable execution rows for a run."""
    async with factory() as session:
        rows = await session.scalars(
            select(ItemExecutionModel).where(ItemExecutionModel.run_id == run_id)
        )
        return list(rows)


# ---------------------------------------------------------------------------
# Scenario A — first execution calls the provider once and records durably
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_execution_calls_provider_once_and_persists_durable_record() -> None:
    factory = await _make_database(ItemExecutionModel.__table__)
    provider = RecordingChatProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    _configure_pipeline(factory, registry)

    result = await activities_mod.execute_item_activity(_item_input(RUN_ID, 0, ITEM_ID))

    assert result.failed is False
    assert result.response == ITEM_ANSWER
    assert provider.calls == 1

    row = await _durable_row(factory, RUN_ID, ITEM_ID)
    assert row is not None
    assert row.response == ITEM_ANSWER
    assert row.prompt == ITEM_PROMPT
    assert row.tokens_input == 7
    assert row.tokens_output == 3


# ---------------------------------------------------------------------------
# Scenario B — re-execution after a durable success does NOT re-call provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_after_durable_success_reuses_result_without_recalling_provider() -> None:
    factory = await _make_database(ItemExecutionModel.__table__)
    provider = RecordingChatProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    _configure_pipeline(factory, registry)
    input_ = _item_input(RUN_ID, 0, ITEM_ID)

    first = await activities_mod.execute_item_activity(input_)
    second = await activities_mod.execute_item_activity(input_)

    assert first.failed is False
    assert second.failed is False
    # Contract: the retry must never re-invoke the provider.
    assert provider.calls == 1
    assert second.response == first.response == ITEM_ANSWER
    assert second.prompt == first.prompt
    row = await _durable_row(factory, RUN_ID, ITEM_ID)
    assert row is not None
    assert row.response == ITEM_ANSWER


# ---------------------------------------------------------------------------
# Scenario C — provider failure persists nothing; a retry may call again
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provider_failure_persists_nothing_and_retry_calls_provider_again() -> None:
    factory = await _make_database(ItemExecutionModel.__table__)
    provider = FailingChatProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    _configure_pipeline(factory, registry)
    input_ = _item_input(RUN_ID, 0, ITEM_ID)

    first = await activities_mod.execute_item_activity(input_)
    second = await activities_mod.execute_item_activity(input_)

    assert first.failed is True
    assert second.failed is True
    assert "simulated provider outage" in (second.error or "")
    # Provider failure surfaces before any durable write: each attempt is
    # a fresh attempt and the provider is legitimately re-invoked.
    assert provider.calls == 2
    assert await _durable_row(factory, RUN_ID, ITEM_ID) is None


# ---------------------------------------------------------------------------
# Scenario D — distinct runs over the same item never reuse each other
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_distinct_runs_over_same_item_do_not_reuse_executions() -> None:
    factory = await _make_database(ItemExecutionModel.__table__)
    provider = RecordingChatProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    _configure_pipeline(factory, registry)

    run_a = await activities_mod.execute_item_activity(_item_input("run-a", 0, ITEM_ID))
    run_b = await activities_mod.execute_item_activity(_item_input("run-b", 0, ITEM_ID))

    assert run_a.failed is False
    assert run_b.failed is False
    assert provider.calls == 2
    assert run_b.response == run_a.response == ITEM_ANSWER
    assert await _durable_row(factory, "run-a", ITEM_ID) is not None
    assert await _durable_row(factory, "run-b", ITEM_ID) is not None


# ---------------------------------------------------------------------------
# Scenario E — a metric that errors does not re-invoke the item provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metric_recomputed_on_retry_without_recalling_item_provider() -> None:
    factory = await _make_database(ItemExecutionModel.__table__)
    provider = RecordingChatProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    metric = CountingMetric()
    engine = MetricEngine()
    engine.register(metric)
    _configure_pipeline(factory, registry, metric_engine=engine)
    input_ = _item_input(RUN_ID, 0, ITEM_ID, metric_names=("counting",))

    first = await activities_mod.execute_item_activity(input_)
    second = await activities_mod.execute_item_activity(input_)

    assert first.failed is False
    assert second.failed is False
    assert provider.calls == 1
    # Metrics are recomputed on the retry against the durable evidence.
    assert metric.calls == 2
    assert len(first.metrics) == 1
    assert len(second.metrics) == 1
    assert second.metrics[0].metric_name == "counting"
    assert second.metrics[0].score == 0.42
    assert second.response == first.response == ITEM_ANSWER
    row = await _durable_row(factory, RUN_ID, ITEM_ID)
    assert row is not None
    assert row.response == ITEM_ANSWER


# ---------------------------------------------------------------------------
# Real Temporal boundary — full workflow with the durable schema active
# ---------------------------------------------------------------------------


@pytest.fixture
async def time_skipping_env():
    """Provide a time-skipping Temporal environment (offline-safe)."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


async def _create_run(factory: async_sessionmaker[Any]) -> str:
    """Create a persisted evaluation run and return its id."""
    async with factory() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = CreateEvaluationRunHandler(repo)
        command = CreateEvaluationRunCommand(
            evaluation_id="idempotency-e2e-evaluation",
            evaluation_name="Idempotency end-to-end",
            provider="recording",
            model="gpt-4o",
            metrics=("json_validity", "token_usage"),
            project_id=None,
            created_by="integration-test",
            tags=["idempotency"],
            workflow_id=None,
        )
        run = await handler.handle(command)
        await session.commit()
        return str(run.id)


def _register_all_activities(worker_activities: Any) -> None:
    """Register the full evaluation worker activity set."""
    from app.evaluation.temporal import activities as activity_module

    for name in (
        "queue_run_activity",
        "start_run_activity",
        "execute_item_activity",
        "persist_metric_results_activity",
        "update_progress_activity",
        "complete_run_activity",
        "fail_run_activity",
        "cancel_run_activity",
        "finalize_run_integrity_activity",
    ):
        worker_activities.append(getattr(activity_module, name))
    return worker_activities


@pytest.mark.asyncio
async def test_workflow_calls_provider_once_per_item_with_durable_schema(
    time_skipping_env,
) -> None:
    """Full chain through a real Temporal worker calls the provider once."""
    factory = await _make_database(
        EvaluationRunModel.__table__,
        MetricResultModel.__table__,
        ItemExecutionModel.__table__,
    )
    provider = RecordingChatProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    metric_engine = MetricEngine()
    for metric_cls in ALL_METRICS:
        metric_engine.register(metric_cls())
    _configure_pipeline(factory, registry, metric_engine=metric_engine)

    run_id = await _create_run(factory)

    async with Worker(
        time_skipping_env.client,
        task_queue="evaluation-idempotency",
        workflows=[EvaluationRunWorkflow],
        activities=_register_all_activities([]),
    ):
        result = await time_skipping_env.client.execute_workflow(
            EvaluationRunWorkflow.run,
            WorkflowInput(
                run_id=run_id,
                total_items=2,
                provider_name="recording",
                model_id="gpt-4o",
                metric_names=("json_validity", "token_usage"),
                dataset_items=(
                    {"item_id": "item-1", "prompt": ITEM_PROMPT},
                    {"item_id": "item-2", "prompt": ITEM_PROMPT},
                ),
            ),
            id=f"evaluation-{run_id}",
            task_queue="evaluation-idempotency",
        )

    assert result.status == "completed"
    assert result.items_completed == 2
    assert result.items_failed == 0
    assert provider.calls == 2

    rows = await _durable_rows_for_run(factory, run_id)
    assert {row.item_id for row in rows} == {"item-1", "item-2"}


# ---------------------------------------------------------------------------
# Scenario F — cancellation at the durable boundary never marks work complete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancellation_at_durable_boundary_marks_nothing_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelling exactly at the durable write fails the item without a record.

    The run-level cancellation flow is covered by the P6-A cancellation
    suites; this test pins the invariant my change added: a cancellation
    during the durable write must not yield a completed item, must not
    leave a partial durable record, and must not re-invoke the provider.
    """
    from temporalio.exceptions import CancelledError as TemporalCancelledError

    factory = await _make_database(ItemExecutionModel.__table__)
    provider = RecordingChatProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    _configure_pipeline(factory, registry)

    async def _cancelling_write(run_id: str, item_id: str, result: Any) -> None:
        raise TemporalCancelledError("cancelled at durable boundary")

    monkeypatch.setattr(activities_mod, "_write_durable_execution", _cancelling_write)

    result = await activities_mod.execute_item_activity(_item_input(RUN_ID, 0, ITEM_ID))

    assert result.failed is True
    assert "cancelled at durable boundary" in (result.error or "")
    assert provider.calls == 1
    assert await _durable_row(factory, RUN_ID, ITEM_ID) is None
