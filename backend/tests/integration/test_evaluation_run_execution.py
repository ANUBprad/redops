"""End-to-end evaluation execution tests.

Proves the full production chain executes for real: Temporal workflow ->
real activities -> ProviderRegistry-resolved provider -> ItemExecutor ->
MetricEngine -> persisted MetricResultModel rows -> COMPLETED run.

Uses a deterministic provider implementing the full BaseProvider contract,
an in-memory SQLite database with real migrations-backed models, and a
time-skipping Temporal environment so no external services are required.
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
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.metrics.implementations import ALL_METRICS
from app.evaluation.temporal.activities import (
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
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.infrastructure.database.repositories.evaluation_run_repository import (
    SqlAlchemyEvaluationRunRepository,
)
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
    """Fully contracted chat provider with deterministic responses.

    Registered into the real ProviderRegistry exactly like production
    providers. Returns a fixed JSON answer for item prompts and a fixed
    parseable verdict when invoked through the JudgeEngine prompt path.
    """

    def __init__(self) -> None:
        self.call_count = 0
        self.received_prompts: list[str] = []

    @property
    def provider_name(self) -> str:
        """Return the unique provider identifier."""
        return "deterministic-test"

    @property
    def metadata(self) -> ProviderMetadata:
        """Return static provider metadata."""
        return ProviderMetadata(
            name=self.provider_name,
            display_name="Deterministic Test Provider",
            description="Deterministic chat provider for integration tests",
        )

    def capabilities(self) -> CapabilitySet:
        """Return supported capabilities."""
        return CapabilitySet.of(
            Capability.CHAT,
            Capability.SYSTEM_PROMPT,
            Capability.MULTI_TURN,
        )

    def supports(self, capability: CapabilitySet) -> bool:
        """Check whether all requested capabilities are supported."""
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
        """Return provider health."""
        return True

    async def detailed_health(self) -> ProviderHealth:
        """Return detailed provider health."""
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
        """Return a deterministic response based on the prompt shape."""
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
            (
                [
                    EvaluationRunModel.__table__,
                    MetricResultModel.__table__,
                ]
            ),
        )
    factory: async_sessionmaker[Any] = async_sessionmaker(engine, expire_on_commit=False)
    return factory


async def _create_run(factory: async_sessionmaker[Any], metrics: tuple[str, ...]) -> str:
    """Create a persisted evaluation run and return its id."""
    async with factory() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = CreateEvaluationRunHandler(repo)
        command = CreateEvaluationRunCommand(
            evaluation_id="e2e-evaluation",
            evaluation_name="End-to-end execution test",
            provider="deterministic-test",
            model="gpt-4o",
            metrics=metrics,
            project_id=None,
            created_by="integration-test",
            tags=["e2e"],
            workflow_id=None,
        )
        run = await handler.handle(command)
        await session.commit()
        return str(run.id)


async def _fetch_metric_rows(
    factory: async_sessionmaker[Any],
    run_id: str,
) -> list[MetricResultModel]:
    """Load persisted metric result rows for a run."""
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
    client = env.client
    task_queue = "evaluation-e2e"
    from app.evaluation.temporal import activities as activity_module

    async with Worker(
        client,
        task_queue=task_queue,
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
        ],
    ):
        result = await client.execute_workflow(
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
            task_queue=task_queue,
        )
    return result


def _configure_pipeline(
    factory: async_sessionmaker[Any],
    registry: ProviderRegistry,
) -> None:
    """Wire the real activity dependencies to the given infrastructure."""
    configure_session_factory(factory)
    configure_provider_registry(registry)
    metric_engine = MetricEngine()
    metric_engine.register_many([metric_cls() for metric_cls in ALL_METRICS])
    configure_metric_engine(metric_engine)
    configure_cost_calculator(build_default_cost_calculator())


@pytest.mark.asyncio
async def test_end_to_end_run_executes_provider_scores_and_persists_results(
    time_skipping_env,
):
    """Full chain: workflow -> provider -> metrics -> DB rows -> COMPLETED run."""
    metric_names = ("json_validity", "token_usage")
    factory = await _build_database()

    registry = ProviderRegistry()
    provider = DeterministicChatProvider()
    registry.register(provider)
    _configure_pipeline(factory, registry)

    run_id = await _create_run(factory, metric_names)

    result = await _run_workflow(
        time_skipping_env,
        run_id=run_id,
        total_items=2,
        metric_names=metric_names,
        dataset_items=(
            {"item_id": "item-1", "prompt": "What is the capital of France?"},
            {"item_id": "item-2", "prompt": "What is the capital of France?"},
        ),
    )

    assert result.status == "completed"
    assert result.items_total == 2
    assert result.items_completed == 2
    assert result.items_failed == 0
    assert provider.call_count == 2

    rows = await _fetch_metric_rows(factory, run_id)
    assert len(rows) == 4

    by_item: dict[str, dict[str, MetricResultModel]] = {}
    for row in rows:
        assert row.error is None
        by_item.setdefault(row.item_id, {})[row.metric_name] = row

    assert set(by_item) == {"item-1", "item-2"}
    for item_rows in by_item.values():
        validity = item_rows["json_validity"]
        token_usage = item_rows["token_usage"]
        assert validity.metadata_json["is_valid"] is True
        assert validity.reasoning == "Valid JSON"
        assert validity.score == 1.0
        assert validity.normalized_score == 1.0
        assert token_usage.metadata_json["tokens_output"] == 5
        assert token_usage.score == 5.0
        assert abs(token_usage.normalized_score - (1.0 - 5 / 4096)) < 1e-9


@pytest.mark.asyncio
async def test_llm_judge_metric_makes_second_real_call_and_persists_verdict(
    time_skipping_env,
):
    """Judge metrics execute a real second provider call through the judge path."""
    metric_names = ("correctness",)
    factory = await _build_database()

    registry = ProviderRegistry()
    provider = DeterministicChatProvider()
    registry.register(provider)
    _configure_pipeline(factory, registry)

    run_id = await _create_run(factory, metric_names)

    result = await _run_workflow(
        time_skipping_env,
        run_id=run_id,
        total_items=1,
        metric_names=metric_names,
        dataset_items=(
            {
                "item_id": "item-j",
                "prompt": "What is the capital of France?",
                "reference": '{"answer": "Paris"}',
            },
        ),
    )

    assert result.status == "completed"
    assert result.items_failed == 0
    assert provider.call_count == 2

    judge_prompts = [p for p in provider.received_prompts if JUDGE_SYSTEM_MARKER in p]
    assert len(judge_prompts) == 1

    rows = await _fetch_metric_rows(factory, run_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.metric_name == "correctness"
    assert row.error is None
    assert row.score == 0.9
    assert row.confidence == 0.8
    assert "deterministic judge verdict" in row.reasoning
    assert row.metadata_json["judge_model"] == "gpt-4o"
    assert row.metadata_json["tokens_output"] == 5
    assert any(JUDGE_SYSTEM_MARKER in p for p in provider.received_prompts)


@pytest.mark.asyncio
async def test_partial_item_failures_still_complete_run_without_metric_rows(
    time_skipping_env,
):
    """A failing provider call marks the item failed; successes still complete."""
    metric_names = ("json_validity",)
    factory = await _build_database()

    class FailOnSecondCallProvider(DeterministicChatProvider):
        """Provider whose second chat call raises."""

        async def chat(
            self,
            messages: list[Message],
            model: str = "",
            options: Any = None,
        ) -> ChatResponse:
            if self.call_count >= 1:
                raise RuntimeError("simulated provider outage")
            return await super().chat(messages, model=model, options=options)

    registry = ProviderRegistry()
    provider = FailOnSecondCallProvider()
    registry.register(provider)
    _configure_pipeline(factory, registry)

    run_id = await _create_run(factory, metric_names)

    result = await _run_workflow(
        time_skipping_env,
        run_id=run_id,
        total_items=2,
        metric_names=metric_names,
        dataset_items=(
            {"item_id": "item-ok", "prompt": "first"},
            {"item_id": "item-bad", "prompt": "second"},
        ),
    )

    assert result.status == "completed"
    assert result.items_total == 2
    assert result.items_completed == 2
    assert result.items_failed == 1

    rows = await _fetch_metric_rows(factory, run_id)
    assert {row.item_id for row in rows} == {"item-ok"}


@pytest.mark.asyncio
async def test_unknown_provider_fails_every_item_and_fails_the_run(
    time_skipping_env,
):
    """An unresolvable provider produces failed results and a FAILED run."""
    metric_names = ("json_validity",)
    factory = await _build_database()

    registry = ProviderRegistry()
    _configure_pipeline(factory, registry)

    run_id = await _create_run(factory, metric_names)

    result = await _run_workflow(
        time_skipping_env,
        run_id=run_id,
        total_items=1,
        metric_names=metric_names,
        provider_name="does-not-exist",
        dataset_items=({"item_id": "item-x", "prompt": "hello"},),
    )

    assert result.status == "failed"
    assert result.items_failed == 1

    rows = await _fetch_metric_rows(factory, run_id)
    assert rows == []
