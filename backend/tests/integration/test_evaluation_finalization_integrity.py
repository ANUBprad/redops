"""P6-C7 tests: evaluation finalization is terminal-state integrity safe.

N13 fix regression suite. Proves that the evaluation workflow never leaves a
run durably COMPLETED (or FAILED) until the integrity records — verdict,
trace_data, provenance, fingerprint — are persisted, and that finalization is
retry-safe and idempotent under Temporal redelivery:

- A  success path: COMPLETED + full integrity records, in one truthful end state
- B  permanent finalize failure: propagated into Temporal retry, run stays
     RUNNING with no verdict — never falsely COMPLETED
- C  transient finalize failure: Temporal retry converges to the same terminal
     state with a single set of metric rows (no duplicates, no invalid
     transition)
- D  crash/redelivery boundary: the DB can never remain COMPLETED-is-the-truth
     just because finalize failed; a redelivered finalize on a terminal run is
     an idempotent overwrite that changes nothing
- E  regression (P6-C2): a finalize retry never re-invokes the provider
- F  regression (P6-C5): metric persistence failure raises out of the activity
     (propagates to Temporal retry) — never swallowed into a fake result
-    cancellation semantics: finalize on an already-CANCELLED run preserves
     CANCELLED (no fabricated terminal transition)

Uses a deterministic fake provider, an in-memory SQLite DB with the real
models, and a time-skipping Temporal environment (no external services).
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.evaluation.application.run_commands import CreateEvaluationRunCommand
from app.evaluation.application.run_handlers import CreateEvaluationRunHandler
from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
from app.evaluation.domain.enums.evaluation_enums import CancellationReason, RunStatus
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.metrics.implementations import ALL_METRICS
from app.evaluation.temporal import activities as activity_module
from app.evaluation.temporal.activities import (
    FinalizeRunIntegrityInput,
    PersistMetricResultsInput,
    configure_cost_calculator,
    configure_metric_engine,
    configure_provider_registry,
    configure_session_factory,
    finalize_run_integrity_activity,
    persist_metric_results_activity,
)
from app.evaluation.temporal.workflow import EvaluationRunWorkflow
from app.evaluation.temporal.workflow import (
    EvaluationRunWorkflowInput as WorkflowInput,
)
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.infrastructure.database.repositories.evaluation_run_repository import (
    SqlAlchemyEvaluationRunRepository,
)
from app.infrastructure.database.repositories.metric_result_repository import (
    SqlAlchemyMetricResultRepository,
)
from app.kernel.entities.base import UUIDv7
from app.providers.capabilities.capability import Capability
from app.providers.capabilities.capability_set import CapabilitySet
from app.providers.cost.defaults import build_default_cost_calculator
from app.providers.health.provider_health import ProviderHealth, ProviderStatus
from app.providers.metadata.provider import ProviderMetadata
from app.providers.models.enums import FinishReason
from app.providers.models.messages import Message
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry

JUDGE_SYSTEM_MARKER = "expert AI evaluation judge"
ITEM_ANSWER = '{"answer": "Paris"}'
JUDGE_VERDICT = '{"score": 0.9, "confidence": 0.8, "reasoning": "deterministic judge verdict"}'


def _message_text(message: Message) -> str:
    """Extract text from a message regardless of content shape."""
    if isinstance(message.content, str):
        return message.content
    return "".join(
        block.text for block in message.content if getattr(block, "text", None) is not None
    )


class DeterministicChatProvider:
    """Deterministic chat provider implementing the real provider contract."""

    def __init__(self) -> None:
        self.call_count = 0
        self.received_prompts: list[str] = []

    @property
    def provider_name(self) -> str:
        return "deterministic-test"

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name=self.provider_name,
            display_name="Deterministic Test Provider",
            description="Deterministic chat provider for integration tests",
        )

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet.of(
            Capability.CHAT,
            Capability.SYSTEM_PROMPT,
            Capability.MULTI_TURN,
        )

    def supports(self, capability: CapabilitySet) -> bool:
        return self.capabilities().supports_all(capability)

    async def initialize(self) -> None:
        """Initialize the provider."""

    async def start(self) -> None:
        """Start accepting requests."""

    async def stop(self) -> None:
        """Stop accepting requests."""

    async def dispose(self) -> None:
        """Release all resources."""

    async def health(self) -> bool:
        return True

    async def detailed_health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_name=self.provider_name,
            status=ProviderStatus.HEALTHY,
        )

    async def chat(
        self,
        messages: list[Message],
        model: str = "",
        options: Any = None,
    ) -> ChatResponse:
        self.call_count += 1
        joined = "\n".join(_message_text(message) for message in messages)
        self.received_prompts.append(joined)
        is_judge_call = JUDGE_SYSTEM_MARKER in joined
        content = JUDGE_VERDICT if is_judge_call else ITEM_ANSWER
        return ChatResponse(
            content=content,
            model=model or "test-model",
            provider=self.provider_name,
            usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
            finish_reason=FinishReason.STOP,
        )


async def _build_database() -> async_sessionmaker[Any]:
    """Create an in-memory SQLite database with the tables under test."""
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            ([EvaluationRunModel.__table__, MetricResultModel.__table__]),
        )
    return async_sessionmaker(engine, expire_on_commit=False)


async def _create_run(
    factory: async_sessionmaker[Any],
    metrics: tuple[str, ...],
    *,
    provider: str = "deterministic-test",
) -> str:
    """Create a persisted evaluation run and return its id."""
    async with factory() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = CreateEvaluationRunHandler(repo)
        command = CreateEvaluationRunCommand(
            evaluation_id="finalization-e2e-evaluation",
            evaluation_name="Finalization end-to-end",
            provider=provider,
            model="gpt-4o",
            metrics=metrics,
            project_id=None,
            created_by="integration-test",
            tags=["finalization"],
            workflow_id=None,
        )
        run = await handler.handle(command)
        await session.commit()
        return str(run.id)


def _configure_pipeline(
    factory: async_sessionmaker[Any],
    registry: ProviderRegistry,
) -> None:
    """Wire the real activity dependencies to the given infrastructure."""
    configure_session_factory(factory)
    configure_provider_registry(registry)
    metric_engine = MetricEngine()
    for metric_cls in ALL_METRICS:
        metric_engine.register(metric_cls())
    configure_metric_engine(metric_engine)
    configure_cost_calculator(build_default_cost_calculator())


async def _run_workflow(
    env: WorkflowEnvironment,
    *,
    run_id: str,
    total_items: int,
    metric_names: tuple[str, ...],
    dataset_items: tuple[dict[str, str], ...],
    provider_name: str = "deterministic-test",
) -> Any:
    """Execute the real workflow on a worker with real activities."""
    async with Worker(
        env.client,
        task_queue="evaluation-finalization",
        workflows=[EvaluationRunWorkflow],
        activities=[
            activity_module.queue_run_activity,
            activity_module.start_run_activity,
            activity_module.execute_item_activity,
            activity_module.persist_metric_results_activity,
            activity_module.update_progress_activity,
            activity_module.complete_run_activity,
            activity_module.fail_run_activity,
            activity_module.cancel_run_activity,
            activity_module.finalize_run_integrity_activity,
        ],
    ):
        return await env.client.execute_workflow(
            EvaluationRunWorkflow.run,
            WorkflowInput(
                run_id=run_id,
                total_items=total_items,
                provider_name=provider_name,
                model_id="gpt-4o",
                metric_names=metric_names,
                dataset_items=dataset_items,
            ),
            id=f"evaluation-{run_id}",
            task_queue="evaluation-finalization",
        )


async def _load_persisted_run(
    factory: async_sessionmaker[Any],
    run_id: str,
) -> EvaluationRun | None:
    """Load a run from the database through the real repository."""
    async with factory() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        return await repo.find_by_id(UUIDv7.from_string(run_id))


async def _metric_rows(factory: async_sessionmaker[Any], run_id: str) -> list[MetricResultModel]:
    """Load all persisted metric rows for a run."""
    async with factory() as session:
        rows = await session.scalars(
            select(MetricResultModel).where(MetricResultModel.run_id == run_id)
        )
        return list(rows)


@pytest.fixture
async def time_skipping_env():
    """Provide a time-skipping Temporal environment (offline-safe)."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


# ---------------------------------------------------------------------------
# A — successful finalization records full integrity before COMPLETED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_finalization_records_full_integrity(
    time_skipping_env,
) -> None:
    """A successful run ends COMPLETED with verdict/trace/provenance/fingerprint."""
    factory = await _build_database()
    registry = ProviderRegistry()
    provider = DeterministicChatProvider()
    registry.register(provider)
    _configure_pipeline(factory, registry)

    run_id = await _create_run(factory, ("correctness",))

    result = await _run_workflow(
        time_skipping_env,
        run_id=run_id,
        total_items=1,
        metric_names=("correctness",),
        dataset_items=(
            {
                "item_id": "item-pass",
                "prompt": "What is the capital of France?",
                "reference": '{"answer": "Paris"}',
            },
        ),
    )

    assert result.status == "completed"
    assert provider.call_count == 2

    run = await _load_persisted_run(factory, run_id)
    assert run is not None
    assert run.status == RunStatus.COMPLETED
    assert run.verdict == "pass"
    assert run.fingerprint is not None and len(run.fingerprint) == 32
    assert run.trace_data is not None
    assert run.trace_data["provider_name"] == "deterministic-test"
    assert len(run.trace_data["item_traces"]) == 1
    assert run.provenance is not None
    assert run.provenance["environment"]["git_commit_hash"]
    assert run.items_completed == 1

    rows = await _metric_rows(factory, run_id)
    assert len(rows) == 1
    assert rows[0].metric_name == "correctness"
    assert rows[0].error is None


# ---------------------------------------------------------------------------
# B + D — permanent finalize failure: run never durably COMPLETED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_permanent_finalize_failure_never_leaves_run_completed(
    time_skipping_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Finalize outage propagates through Temporal retries; run stays RUNNING.

    Regression for N13: the OLD ordering committed COMPLETED first, so a
    finalize outage left the run permanently COMPLETED-without-verdict.
    """
    factory = await _build_database()
    registry = ProviderRegistry()
    provider = DeterministicChatProvider()
    registry.register(provider)
    _configure_pipeline(factory, registry)

    run_id = await _create_run(factory, ("correctness",))

    calls = 0

    async def _always_boom(self: object, *, run_id: object, metric_name: object) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("finalize outage")

    monkeypatch.setattr(
        SqlAlchemyMetricResultRepository,
        "find_by_run_id",
        _always_boom,
    )

    with pytest.raises(WorkflowFailureError):
        await _run_workflow(
            time_skipping_env,
            run_id=run_id,
            total_items=1,
            metric_names=("correctness",),
            dataset_items=({"item_id": "item-1", "prompt": "What is 2+2?"},),
        )

    assert calls == 3

    run = await _load_persisted_run(factory, run_id)
    assert run is not None
    assert run.status == RunStatus.RUNNING
    assert run.verdict is None


# ---------------------------------------------------------------------------
# C — transient finalize failure converges; D — redelivery is idempotent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transient_finalize_failure_converges_without_duplicates(
    time_skipping_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A first-attempt finalize failure is retried by Temporal and converges.

    Asserts the retry produces the SAME terminal state, no duplicate metric
    rows, and no invalid transition (RUNNING -> COMPLETED is the only one).
    """
    factory = await _build_database()
    registry = ProviderRegistry()
    provider = DeterministicChatProvider()
    registry.register(provider)
    _configure_pipeline(factory, registry)

    run_id = await _create_run(factory, ("correctness",))

    real_find = SqlAlchemyMetricResultRepository.find_by_run_id
    calls = 0
    failed_once = False

    async def _fail_then_real(self: object, *, run_id: object, metric_name: object) -> Any:
        nonlocal calls, failed_once
        calls += 1
        if not failed_once:
            failed_once = True
            raise RuntimeError("transient finalize outage")
        return await real_find(self, run_id=run_id, metric_name=metric_name)

    monkeypatch.setattr(
        SqlAlchemyMetricResultRepository,
        "find_by_run_id",
        _fail_then_real,
    )

    result = await _run_workflow(
        time_skipping_env,
        run_id=run_id,
        total_items=1,
        metric_names=("correctness",),
        dataset_items=(
            {
                "item_id": "item-pass",
                "prompt": "What is the capital of France?",
                "reference": '{"answer": "Paris"}',
            },
        ),
    )

    assert result.status == "completed"
    assert calls == 2

    run = await _load_persisted_run(factory, run_id)
    assert run is not None
    assert run.status == RunStatus.COMPLETED
    assert run.verdict == "pass"

    rows = await _metric_rows(factory, run_id)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_finalize_redelivery_on_completed_run_is_idempotent(
    time_skipping_env,
) -> None:
    """Re-delivered finalize on an already-COMPLETED run changes nothing."""
    factory = await _build_database()
    registry = ProviderRegistry()
    provider = DeterministicChatProvider()
    registry.register(provider)
    _configure_pipeline(factory, registry)

    run_id = await _create_run(factory, ("correctness",))

    result = await _run_workflow(
        time_skipping_env,
        run_id=run_id,
        total_items=1,
        metric_names=("correctness",),
        dataset_items=(
            {
                "item_id": "item-pass",
                "prompt": "What is the capital of France?",
                "reference": '{"answer": "Paris"}',
            },
        ),
    )
    assert result.status == "completed"

    run = await _load_persisted_run(factory, run_id)
    assert run is not None
    original_verdict = run.verdict
    original_fingerprint = run.fingerprint

    new_verdict = await finalize_run_integrity_activity(
        FinalizeRunIntegrityInput(
            run_id=run_id,
            metric_names=("correctness",),
            trace_data={"run_id": run_id, "item_traces": []},
            fingerprint=original_fingerprint,
        )
    )

    run_after = await _load_persisted_run(factory, run_id)
    assert run_after is not None
    assert run_after.status == RunStatus.COMPLETED
    assert run_after.verdict == new_verdict == original_verdict
    assert run_after.fingerprint == original_fingerprint


# ---------------------------------------------------------------------------
# E — P6-C2 regression: no provider re-invocation across a finalize retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_retry_never_reinvokes_provider(
    time_skipping_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Durable execution is preserved: only item + judge provider calls happen."""
    factory = await _build_database()
    registry = ProviderRegistry()
    provider = DeterministicChatProvider()
    registry.register(provider)
    _configure_pipeline(factory, registry)

    run_id = await _create_run(factory, ("correctness",))

    real_find = SqlAlchemyMetricResultRepository.find_by_run_id
    failed_once = False

    async def _fail_then_real(self: object, *, run_id: object, metric_name: object) -> Any:
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise RuntimeError("transient finalize outage")
        return await real_find(self, run_id=run_id, metric_name=metric_name)

    monkeypatch.setattr(
        SqlAlchemyMetricResultRepository,
        "find_by_run_id",
        _fail_then_real,
    )

    result = await _run_workflow(
        time_skipping_env,
        run_id=run_id,
        total_items=1,
        metric_names=("correctness",),
        dataset_items=(
            {
                "item_id": "item-pass",
                "prompt": "What is the capital of France?",
                "reference": '{"answer": "Paris"}',
            },
        ),
    )

    assert result.status == "completed"
    assert provider.call_count == 2


# ---------------------------------------------------------------------------
# F — P6-C5 regression: metric persistence failure is not swallowed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metric_persistence_failure_propagates_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A metric persistence outage raises out of the activity (retryable)."""
    factory = await _build_database()
    registry = ProviderRegistry()
    provider = DeterministicChatProvider()
    registry.register(provider)
    _configure_pipeline(factory, registry)

    run_id = await _create_run(factory, ("correctness",))

    async def _boom(self: object, results: object) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(
        SqlAlchemyMetricResultRepository,
        "save_many",
        _boom,
    )

    payload = activity_module.MetricResultPayload(
        metric_name="correctness",
        score=0.9,
        normalized_score=0.9,
        confidence=0.8,
        reasoning="deterministic",
        version="1.0.0",
        cost_usd=0.001,
        execution_time_ms=100,
    )

    with pytest.raises(RuntimeError, match="disk full"):
        await persist_metric_results_activity(
            PersistMetricResultsInput(
                run_id=run_id,
                item_id="item-1",
                results=(payload,),
            )
        )

    run = await _load_persisted_run(factory, run_id)
    assert run is not None
    assert run.status == RunStatus.CREATED


# ---------------------------------------------------------------------------
# Cancellation semantics: finalize never fabricates a terminal transition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_preserves_cancelled_terminal_state() -> None:
    """Finalizing an already-CANCELLED run must leave it CANCELLED."""
    factory = await _build_database()
    registry = ProviderRegistry()
    provider = DeterministicChatProvider()
    registry.register(provider)
    _configure_pipeline(factory, registry)

    run_id = await _create_run(factory, ("correctness",))

    async with factory() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        run = await repo.find_by_id(UUIDv7.from_string(run_id))
        assert run is not None
        run.queue()
        run.start(total_items=1)
        run.cancel(reason=CancellationReason("user_cancelled"), force=True)
        await repo.save(run)
        await session.commit()

    verdict = await finalize_run_integrity_activity(
        FinalizeRunIntegrityInput(
            run_id=run_id,
            metric_names=("correctness",),
            trace_data={"run_id": run_id, "item_traces": []},
            fingerprint="p6c7-cancelled-run",
        )
    )

    run_after = await _load_persisted_run(factory, run_id)
    assert run_after is not None
    assert verdict in ("pass", "fail", "error")
    assert run_after.status == RunStatus.CANCELLED
    assert run_after.trace_data is not None
    assert run_after.fingerprint == "p6c7-cancelled-run"
