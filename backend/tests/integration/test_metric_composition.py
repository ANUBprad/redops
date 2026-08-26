"""Cross-metric composition test through the real evaluation pipeline.

Proves all 22 registered metrics execute together over the eight
canonical fixtures using the real production composition:

EvaluationPipelineExecutor -> ProviderInvocationStage (registry-resolved
provider via RuntimeCoordinator) -> MetricDispatchStage (MetricEngine)
-> AggregationStage -> PersistenceStage -> SqlAlchemyMetricResultRepository.

Nothing is mocked: the only fakes sit at the provider boundary (chat +
embedding), exactly like the E2E workflow test.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, ClassVar

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.evaluation.domain.value_objects.evaluation_value_objects import (
    EvaluationConfiguration,
    EvaluationMetadata,
    EvaluationProfile,
    EvaluationType,
)
from app.evaluation.execution.context.context import (
    MetricSelection,
    PipelineContext,
    ProviderSelection,
)
from app.evaluation.execution.pipeline.pipeline import ExecutionPipeline
from app.evaluation.execution.pipeline.plan import ExecutionPlan
from app.evaluation.execution.pipeline.step import ExecutionStep
from app.evaluation.execution.results.results import ExecutionOutcome
from app.evaluation.execution.stages.stage import ExecutionStage
from app.evaluation.execution.stages.types import StageType
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.metrics.implementations import ALL_METRICS
from app.evaluation.orchestration.executor import (
    AggregationStage,
    EvaluationPipelineExecutor,
    MetricDispatchStage,
    PersistenceStage,
    ProviderInvocationStage,
)
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.infrastructure.database.repositories.metric_result_repository import (
    SqlAlchemyMetricResultRepository,
)
from app.providers.capabilities.capability import Capability
from app.providers.capabilities.capability_set import CapabilitySet
from app.providers.health.provider_health import ProviderHealth, ProviderStatus
from app.providers.metadata.provider import ProviderMetadata
from app.providers.models.enums import FinishReason
from app.providers.models.messages import Message
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry
from app.providers.runtime.execution.runtime_coordinator import RuntimeCoordinator
from tests.evaluation.fixtures.canonical_items import CANONICAL_ITEMS

ITEM_ANSWER = '{"answer": "Paris"}'
JUDGE_SYSTEM_MARKER = "expert AI evaluation judge"
JUDGE_VERDICT = '{"score": 0.9, "confidence": 0.8, "reasoning": "composition verdict"}'


def _all_metric_names(engine: MetricEngine) -> tuple[str, ...]:
    return tuple(sorted(d.name for d in engine.list_definitions()))


def _message_text(message: Message) -> str:
    """Extract text from a message regardless of content shape."""
    if isinstance(message.content, str):
        return message.content
    return "".join(
        block.text for block in message.content if getattr(block, "text", None) is not None
    )


class DeterministicChatProvider:
    """Fully contracted chat provider with deterministic responses."""

    @property
    def provider_name(self) -> str:
        """Return the unique provider identifier."""
        return "deterministic-composition"

    @property
    def metadata(self) -> ProviderMetadata:
        """Return static provider metadata."""
        return ProviderMetadata(
            name=self.provider_name,
            display_name="Deterministic Composition Provider",
            description="Chat provider for the cross-metric composition test",
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
        """Return a fixed JSON answer or judge verdict by prompt shape."""
        joined = "\n".join(_message_text(message) for message in messages)
        is_judge_call = JUDGE_SYSTEM_MARKER in joined
        content = JUDGE_VERDICT if is_judge_call else ITEM_ANSWER
        return ChatResponse(
            content=content,
            model=model or "composition-model",
            provider=self.provider_name,
            usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
            finish_reason=FinishReason.STOP,
        )


class DeterministicEmbeddingProvider:
    """Embedding-only provider with fixed vectors per text."""

    VECTORS: ClassVar[dict[str, tuple[float, ...]]] = {
        "Paris is the capital of France.": (1.0, 0.0, 0.0),
        "The capital of France is Berlin.": (1.0, 0.0, 0.0),
    }

    @property
    def provider_name(self) -> str:
        """Return the unique provider identifier."""
        return "scripted-composition-embeddings"

    @property
    def metadata(self) -> ProviderMetadata:
        """Return static provider metadata."""
        return ProviderMetadata(
            name=self.provider_name,
            display_name="Scripted Composition Embeddings",
            description="Embedding provider for the cross-metric composition test",
        )

    def capabilities(self) -> CapabilitySet:
        """Return supported capabilities."""
        return CapabilitySet.of(Capability.EMBEDDING)

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

    async def embed(
        self,
        texts: list[str],
        *,
        model: str = "",
        options: Any = None,
    ) -> Any:
        """Return deterministic unit-ish vectors for every text."""
        from app.providers.models.responses import EmbeddingResponse

        vector = tuple(self.VECTORS.get(texts[0], (0.5, 0.5, 0.5)))
        return EmbeddingResponse(
            embedding=vector,
            dimensions=len(vector),
            model=model or "composition-embed-model",
            provider=self.provider_name,
            usage=Usage(input_tokens=len(texts), output_tokens=0, total_tokens=len(texts)),
        )


async def _build_metric_result_factory() -> async_sessionmaker[Any]:
    """Create an in-memory SQLite factory with the metric-result table."""
    engine = create_async_engine("sqlite+aiosqlite://")
    # Known migration quirk: creating all tables at once fails on a
    # duplicated index name; create only what this test exercises.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, ([MetricResultModel.__table__]))
    return async_sessionmaker(engine, expire_on_commit=False)


class SessionScopedResultRepository:
    """Binds the real repository to a fresh session per save, like the
    production activity does with its session factory."""

    def __init__(self, factory: async_sessionmaker[Any]) -> None:
        self._factory = factory

    async def save_many(self, results: Any) -> None:
        async with self._factory() as session:
            await SqlAlchemyMetricResultRepository(session).save_many(results)
            await session.commit()


def _build_plan() -> ExecutionPlan:
    """Build a four-stage plan over the canonical fixtures."""
    steps: list[ExecutionStep] = []
    for index, item in enumerate(CANONICAL_ITEMS):
        steps.append(
            ExecutionStep.create(
                stage_type=StageType.PROVIDER_INVOCATION,
                name=f"invoke-{item.key}",
                item_index=index,
                order=index * 2,
                metadata={
                    "prompt": item.prompt,
                    "reference": item.reference,
                    "context": item.context,
                    "item_id": item.key,
                },
            )
        )
        steps.append(
            ExecutionStep.create(
                stage_type=StageType.METRIC_DISPATCH,
                name=f"score-{item.key}",
                item_index=index,
                order=index * 2 + 1,
                metadata={
                    "prompt": item.prompt,
                    "reference": item.reference,
                    "context": item.context,
                    "item_id": item.key,
                    **({"schema": json.dumps(item.schema)} if item.schema is not None else {}),
                },
            )
        )
    return ExecutionPlan.create(
        uuid.uuid4(),
        stages=(
            StageType.PROVIDER_INVOCATION,
            StageType.METRIC_DISPATCH,
            StageType.AGGREGATION,
            StageType.PERSISTENCE,
        ),
        steps=steps,
        total_items=len(CANONICAL_ITEMS),
    )


class StateCaptureStage(ExecutionStage):
    """Test instrumentation: copies shared state out of the pipeline.

    Sits after aggregation so the test can assert on dispatch and
    aggregation artifacts without touching production stages.
    """

    def __init__(self, captured: dict[str, Any]) -> None:
        super().__init__(stage_type=StageType.AGGREGATION, name="StateCapture")
        self._captured = captured

    def validate(self, context: PipelineContext) -> list[Any]:
        return []

    async def execute(
        self,
        context: PipelineContext,
        steps: Any,
        shared_state: dict[str, Any] | None = None,
    ) -> Any:
        from datetime import UTC, datetime

        if shared_state is not None:
            self._captured.update(shared_state)
        from app.evaluation.execution.results.results import StageResult

        return StageResult(
            stage_type=self.stage_type,
            stage_name=self.name,
            outcome=ExecutionOutcome.SUCCESS,
            completed_at=datetime.now(UTC),
        )

    async def rollback(self, context: PipelineContext, result: Any) -> None:
        pass

    def supports_resume(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_all_metrics_execute_together_over_canonical_fixtures() -> None:
    """Run every registered metric across all fixtures via the real pipeline."""
    engine = MetricEngine()
    engine.register_many([metric_cls() for metric_cls in ALL_METRICS])

    metric_names = _all_metric_names(engine)

    registry = ProviderRegistry()
    chat_provider = DeterministicChatProvider()
    embedding_provider = DeterministicEmbeddingProvider()
    registry.register(chat_provider)
    registry.register(embedding_provider)

    factory = await _build_metric_result_factory()
    repository = SessionScopedResultRepository(factory)

    plan = _build_plan()
    config = EvaluationConfiguration(
        name="canonical-composition-run",
        eval_type=EvaluationType.SINGLE,
        profile=EvaluationProfile(provider_name="deterministic-composition"),
        metrics=list(metric_names),
        prompt_template="{prompt}",
    )
    context = PipelineContext(
        run_id=plan.run_id,
        evaluation_name="canonical-composition-run",
        plan=plan,
        config=config,
        profile=config.profile,
        metadata=EvaluationMetadata(
            judge_provider=chat_provider.provider_name,
            embedding_provider=embedding_provider.provider_name,
        ),
        provider_selection=ProviderSelection(
            provider_name=chat_provider.provider_name,
            model_id="composition-model",
        ),
        metric_selection=MetricSelection(metric_names=metric_names),
    )

    captured: dict[str, Any] = {}
    pipeline = ExecutionPipeline(
        plan=plan,
        stages=(
            ProviderInvocationStage(registry, RuntimeCoordinator()),
            MetricDispatchStage(engine, provider_registry=registry),
            AggregationStage(engine),
            PersistenceStage(metric_result_repository=repository),
            StateCaptureStage(captured),
        ),
    )

    result = await EvaluationPipelineExecutor().execute(pipeline, context)

    assert result.outcome == ExecutionOutcome.SUCCESS

    # --- dispatch: 22 metric results per fixture -------------------------
    metric_results: dict[int, list[Any]] = captured["metric_results"]
    assert set(metric_results.keys()) == set(range(len(CANONICAL_ITEMS)))
    for results in metric_results.values():
        assert len(results) == len(metric_names)

    for index, item in enumerate(CANONICAL_ITEMS):
        by_name = {r.metric_name: r for r in metric_results[index]}
        assert set(by_name.keys()) == set(metric_names)
        has_context = bool(item.context)

        # No silent fabrications: every failure is an explicit error.
        for r in by_name.values():
            if not r.is_success:
                assert r.error, f"{item.key}/{r.metric_name} failed silently"
                assert r.normalized_score == 0.0

        # Deterministic contract scores hold on every fixture.
        assert by_name["json_validity"].normalized_score == 1.0
        assert by_name["token_usage"].normalized_score == pytest.approx(1 - 5 / 4096)
        if item.schema is not None:
            assert by_name["schema_validation"].normalized_score == 1.0
        else:
            assert not by_name["schema_validation"].is_success

        # Embedding metrics executed with provenance recorded.
        sim = by_name["semantic_similarity"]
        if item.reference:
            assert sim.is_success
            assert sim.metadata["embedding_provider"] == "scripted-composition-embeddings"
            assert sim.metadata["embedding_model"] == "composition-embed-model"
        else:
            assert not sim.is_success
            assert "reference" in (sim.error or "")

        # Judge metrics executed with provenance recorded.
        faithfulness = by_name["faithfulness"]
        if has_context:
            assert faithfulness.is_success
            assert faithfulness.metadata["provider"] == "deterministic-composition"
            assert faithfulness.metadata["judge_model"] == "composition-model"
            assert faithfulness.normalized_score == pytest.approx(0.9)
        else:
            # honest refusal without evaluation material
            assert not faithfulness.is_success
            assert "context" in (faithfulness.error or "")

        # Context-dependent metrics succeed exactly when context exists.
        context_metrics = [by_name["context_relevance"], by_name["groundedness"]]
        for cm in context_metrics:
            assert cm.is_success == has_context, (
                f"{item.key}/{cm.metric_name} success={cm.is_success}, expected {has_context}"
            )

    # --- aggregation covers every metric, honestly ------------------------
    aggregations: dict[str, Any] = captured["aggregations"]
    assert set(aggregations.keys()) == set(metric_names)
    context_item_count = sum(1 for item in CANONICAL_ITEMS if item.context)
    for name in metric_names:
        agg = aggregations[name]
        assert agg.success_count + agg.error_count == len(CANONICAL_ITEMS), (
            f"{name} aggregation incomplete"
        )
    assert aggregations["context_relevance"].success_count == context_item_count
    assert aggregations["context_relevance"].error_count == (
        len(CANONICAL_ITEMS) - context_item_count
    )

    # --- persistence round-trips everything ------------------------------
    async with factory() as session:
        rows = (
            (await session.execute(select(MetricResultModel).order_by(MetricResultModel.id)))
            .scalars()
            .all()
        )
    assert len(rows) == len(CANONICAL_ITEMS) * len(metric_names)

    persisted_faithfulness = [row for row in rows if row.metric_name == "faithfulness"]
    assert len(persisted_faithfulness) == len(CANONICAL_ITEMS)
    context_keys = {item.key for item in CANONICAL_ITEMS if item.context}
    for row in persisted_faithfulness:
        if row.item_id in context_keys:
            assert row.score == pytest.approx(0.9), f"{row.item_id} faithfulness"
        else:
            assert row.score == 0.0 and row.error, f"{row.item_id} faithfulness"
    assert {row.item_id for row in persisted_faithfulness} == {item.key for item in CANONICAL_ITEMS}
