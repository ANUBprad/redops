"""Integration tests for real item execution through the evaluation pipeline.

Proves that dataset items flow into provider invocations as real prompts,
that provider calls return real token usage, cost, and latency metadata,
and that the Temporal activity path shares the same executor logic.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.evaluation.data.dataset import DatasetItem, EvaluationDataset
from app.evaluation.data.store import InMemoryDatasetStore
from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
from app.evaluation.domain.enums.evaluation_enums import EvaluationType
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    DatasetReference,
    EvaluationConfiguration,
    EvaluationProfile,
    ExecutionBudget,
    ExecutionLimits,
    ExecutionPolicy,
)
from app.evaluation.execution.context.context import (
    MetricSelection,
    PipelineContext,
    ProviderSelection,
    TraceIdentifiers,
)
from app.evaluation.execution.item_executor import ItemExecutor
from app.evaluation.execution.prompt_builder import PromptTemplate
from app.evaluation.orchestration.executor import ProviderInvocationStage
from app.evaluation.orchestration.planner import EvaluationPlanner
from app.providers.cost.defaults import build_default_cost_calculator
from app.providers.models.enums import FinishReason, MessageRole
from app.providers.models.messages import Message
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry
from app.providers.runtime.execution.runtime_coordinator import RuntimeCoordinator


class RecordingChatProvider:
    """Chat provider stub that records the messages it receives."""

    provider_name = "openai"

    def __init__(self, response_text: str = "The answer is 42.") -> None:
        self._response_text = response_text
        self.received_messages: list[Message] = []
        self.call_count = 0

    async def chat(
        self,
        messages: list[Message],
        model: str = "",
        options: Any = None,
    ) -> ChatResponse:
        self.call_count += 1
        self.received_messages.extend(messages)
        return ChatResponse(
            content=self._response_text,
            model=model or "gpt-4o",
            provider=self.provider_name,
            usage=Usage(input_tokens=1000, output_tokens=2000, total_tokens=3000),
            finish_reason=FinishReason.STOP,
        )


def _message_text(message: Message) -> str:
    """Extract the text from a message regardless of content shape."""
    if isinstance(message.content, str):
        return message.content
    return "".join(
        block.text for block in message.content if getattr(block, "text", None) is not None
    )


def _build_run(
    *,
    dataset_id: str,
    row_count: int,
    system_prompt: str | None = None,
    prompt_template: str | None = None,
) -> EvaluationRun:
    """Build an EvaluationRun referencing a dataset."""
    profile = EvaluationProfile(
        provider_name="openai",
        model_id="gpt-4o",
        temperature=0.0,
        system_prompt=system_prompt,
    )
    config = EvaluationConfiguration(
        name="Real Item Execution Test",
        eval_type=EvaluationType.DATASET,
        profile=profile,
        dataset=DatasetReference(dataset_id=dataset_id, row_count=row_count),
        metrics=("accuracy",),
        budget=ExecutionBudget(max_cost_usd=10.0, max_tokens=10_000, max_duration_seconds=300),
        limits=ExecutionLimits(max_concurrency=1, batch_size=10, checkpoint_interval=5),
        policy=ExecutionPolicy(
            continue_on_item_failure=True,
            max_retries_per_item=0,
            timeout_per_item_seconds=30,
        ),
        prompt_template=prompt_template,
    )
    return EvaluationRun(
        evaluation_name=config.name,
        config=config,
        profile=profile,
    )


def _build_store(items: tuple[DatasetItem, ...], dataset_id: str) -> InMemoryDatasetStore:
    """Build a dataset store pre-populated with items."""
    dataset = EvaluationDataset(name="real-items", items=items)
    return InMemoryDatasetStore({dataset_id: dataset})


def _build_context(
    run: EvaluationRun,
    plan: Any,
) -> PipelineContext:
    """Build a PipelineContext for a run and plan."""
    return PipelineContext(
        run_id=run.id,
        evaluation_name=run.evaluation_name,
        plan=plan,
        config=run.config,
        profile=run.profile,
        metadata=run.metadata,
        provider_selection=ProviderSelection(provider_name="openai", model_id="gpt-4o"),
        metric_selection=MetricSelection(metric_names=("accuracy",)),
        trace=TraceIdentifiers.from_correlation_id(str(run.id)),
    )


class TestItemExecutorRealPrompt:
    """Prove ItemExecutor sends real rendered prompts to the provider."""

    async def test_prompt_and_tokens_flow_to_provider(self) -> None:
        """The exact item prompt reaches the provider with real usage."""
        provider = RecordingChatProvider("Paris is the capital.")
        item = DatasetItem(
            prompt="What is the capital of France?",
            reference="Paris",
            context="Geography",
        )

        executor = ItemExecutor(
            build_default_cost_calculator(),
            prompt_template=PromptTemplate(template="{prompt}"),
        )
        result = await executor.execute(
            provider,
            provider_name="openai",
            model_id="gpt-4o",
            item=item,
            item_index=0,
        )

        assert result.is_success
        assert provider.call_count == 1
        assert _message_text(provider.received_messages[0]) == "What is the capital of France?"
        assert provider.received_messages[0].role == MessageRole.USER
        assert result.tokens_input == 1000
        assert result.tokens_output == 2000
        assert result.latency_ms >= 0
        assert result.finish_reason == "stop"

    async def test_system_prompt_prepended(self) -> None:
        """A configured system prompt is sent as the first message."""
        provider = RecordingChatProvider()
        item = DatasetItem(prompt="Summarize this.")

        executor = ItemExecutor(
            build_default_cost_calculator(),
            prompt_template=PromptTemplate(
                template="{prompt}",
                system_prompt="You are a helpful assistant.",
            ),
        )
        result = await executor.execute(
            provider,
            provider_name="openai",
            model_id="gpt-4o",
            item=item,
            item_index=0,
        )

        assert result.is_success
        assert len(provider.received_messages) == 2
        assert provider.received_messages[0].role == MessageRole.SYSTEM
        assert _message_text(provider.received_messages[0]) == "You are a helpful assistant."
        assert provider.received_messages[1].role == MessageRole.USER
        assert _message_text(provider.received_messages[1]) == "Summarize this."

    async def test_template_variables_rendered(self) -> None:
        """Template variables render from item fields."""
        provider = RecordingChatProvider()
        item = DatasetItem(
            prompt="raw prompt",
            context="background passage",
            reference="golden answer",
        )

        executor = ItemExecutor(
            build_default_cost_calculator(),
            prompt_template=PromptTemplate(
                template="Context: {context}\nQuestion: {prompt}\nReference: {reference}",
            ),
        )
        result = await executor.execute(
            provider,
            provider_name="openai",
            model_id="gpt-4o",
            item=item,
            item_index=0,
        )

        assert result.is_success
        assert _message_text(provider.received_messages[0]) == (
            "Context: background passage\nQuestion: raw prompt\nReference: golden answer"
        )


class TestItemExecutorRealCost:
    """Prove ItemExecutor estimates real USD costs from token usage."""

    async def test_cost_matches_default_pricing(self) -> None:
        """gpt-4o cost equals real per-token pricing (input 2.5/M, output 10/M)."""
        provider = RecordingChatProvider()
        item = DatasetItem(prompt="Question")

        executor = ItemExecutor(build_default_cost_calculator())
        result = await executor.execute(
            provider,
            provider_name="openai",
            model_id="gpt-4o",
            item=item,
            item_index=0,
        )

        expected = (1000 / 1_000_000 * 2.50) + (2000 / 1_000_000 * 10.00)
        assert result.cost_estimated is True
        assert result.cost_usd == pytest.approx(expected, abs=1e-9)

    async def test_unknown_model_reports_unestimated_zero_cost(self) -> None:
        """Unknown models produce zero cost flagged as unestimated."""
        provider = RecordingChatProvider()
        item = DatasetItem(prompt="Question")

        executor = ItemExecutor(build_default_cost_calculator())
        result = await executor.execute(
            provider,
            provider_name="openai",
            model_id="unknown-model-xyz",
            item=item,
            item_index=0,
        )

        assert result.cost_estimated is False
        assert result.cost_usd == 0.0

    async def test_failed_call_returns_failed_result(self) -> None:
        """Provider exceptions surface as a failed result, not a crash."""

        class FailingProvider(RecordingChatProvider):
            async def chat(
                self,
                messages: list[Message],
                model: str = "",
                options: Any = None,
            ) -> ChatResponse:
                msg = "Provider unavailable"
                raise RuntimeError(msg)

        executor = ItemExecutor(build_default_cost_calculator())
        result = await executor.execute(
            FailingProvider(),
            provider_name="openai",
            model_id="gpt-4o",
            item=DatasetItem(prompt="Question"),
            item_index=0,
        )

        assert result.is_success is False
        assert result.error == "Provider unavailable"
        assert result.cost_usd == 0.0


class TestPlannerRealItems:
    """Prove the planner embeds real dataset items into step metadata."""

    async def test_steps_carry_real_item_data(self) -> None:
        """Step metadata contains prompt/reference/context from the store."""
        items = (
            DatasetItem(prompt="P1", reference="R1", context="C1", id="i-1"),
            DatasetItem(prompt="P2", reference="R2", context="C2", id="i-2"),
        )
        store = _build_store(items, "ds-real-1")
        run = _build_run(dataset_id="ds-real-1", row_count=2)

        planner = EvaluationPlanner(dataset_store=store)
        plan = await planner.plan(run)

        assert plan.total_items == 2
        assert len(plan.steps) == 2
        step_meta = plan.steps[0].metadata
        assert step_meta["prompt"] == "P1"
        assert step_meta["reference"] == "R1"
        assert step_meta["context"] == "C1"
        assert step_meta["item_id"] == "i-1"

    async def test_missing_dataset_falls_back_to_row_count(self) -> None:
        """Unknown datasets fall back to row_count with empty item data."""
        run = _build_run(dataset_id="ds-missing", row_count=2)
        planner = EvaluationPlanner(dataset_store=_build_store((), "ds-other"))

        plan = await planner.plan(run)

        assert plan.total_items == 2
        assert plan.steps[0].metadata.get("prompt", "") == ""


class TestProviderInvocationStageRealExecution:
    """Prove the pipeline stage sends real prompts and records real metadata."""

    async def test_stage_executes_real_item_with_metadata(self) -> None:
        """Provider receives the real prompt; step metadata carries usage/cost/latency."""
        provider = RecordingChatProvider()
        registry = ProviderRegistry()
        registry.register(provider)

        items = (
            DatasetItem(
                prompt="What is 6*7?",
                reference="42",
                context="Arithmetic",
                id="i-1",
            ),
        )
        store = _build_store(items, "ds-stage-1")
        run = _build_run(
            dataset_id="ds-stage-1",
            row_count=1,
            system_prompt="Answer concisely.",
        )

        planner = EvaluationPlanner(dataset_store=store)
        plan = await planner.plan(run)
        context = _build_context(run, plan)

        stage = ProviderInvocationStage(
            registry,
            RuntimeCoordinator(),
            cost_calculator=build_default_cost_calculator(),
        )
        steps = plan.steps_for_stage(plan.stages[0])
        result = await stage.execute(context, steps, shared_state={})

        assert result.is_success
        assert result.items_succeeded == 1

        # Real prompt with system message reached the provider.
        assert provider.call_count == 1
        assert provider.received_messages[0].role == MessageRole.SYSTEM
        assert _message_text(provider.received_messages[0]) == "Answer concisely."
        assert provider.received_messages[1].role == MessageRole.USER
        assert _message_text(provider.received_messages[1]) == "What is 6*7?"

        step_result = result.step_results[0]
        assert step_result.metadata["tokens_input"] == "1000"
        assert step_result.metadata["tokens_output"] == "2000"
        assert step_result.metadata["finish_reason"] == "stop"
        assert step_result.metadata["cost_estimated"] == "true"
        assert int(step_result.metadata["latency_ms"]) >= 0

        expected_cost = (1000 / 1_000_000 * 2.50) + (2000 / 1_000_000 * 10.00)
        assert float(step_result.metadata["cost_usd"]) == pytest.approx(
            expected_cost,
            abs=1e-9,
        )

    async def test_stage_shared_state_carries_execution_data(self) -> None:
        """Shared state exposes item executions for metric dispatch."""
        provider = RecordingChatProvider()
        registry = ProviderRegistry()
        registry.register(provider)

        items = (DatasetItem(prompt="P1", reference="R1"),)
        store = _build_store(items, "ds-stage-2")
        run = _build_run(dataset_id="ds-stage-2", row_count=1)

        planner = EvaluationPlanner(dataset_store=store)
        plan = await planner.plan(run)
        context = _build_context(run, plan)

        shared_state: dict[str, Any] = {}
        stage = ProviderInvocationStage(
            registry,
            RuntimeCoordinator(),
            cost_calculator=build_default_cost_calculator(),
        )
        steps = plan.steps_for_stage(plan.stages[0])
        await stage.execute(context, steps, shared_state=shared_state)

        executions = shared_state["item_executions"]
        assert 0 in executions
        assert executions[0]["tokens_input"] == "1000"
        assert executions[0]["tokens_output"] == "2000"
        assert executions[0]["cost_estimated"] == "true"
        assert int(executions[0]["latency_ms"]) >= 0


class TestTemporalActivitySharesExecutor:
    """Prove the Temporal item activity uses the same real executor logic."""

    async def test_execute_item_activity_real_prompt_and_cost(self) -> None:
        """The activity sends real prompts and returns real cost/tokens."""
        from app.evaluation.temporal import activities as activities_mod
        from app.evaluation.temporal.activities import (
            ExecuteItemInput,
            configure_cost_calculator,
            configure_provider_registry,
        )

        provider = RecordingChatProvider()
        registry = ProviderRegistry()
        registry.register(provider)

        old_registry = activities_mod._provider_registry
        old_calculator = activities_mod._cost_calculator
        try:
            configure_provider_registry(registry)
            configure_cost_calculator(build_default_cost_calculator())

            result = await activities_mod.execute_item_activity(
                ExecuteItemInput(
                    run_id="run-1",
                    item_index=0,
                    provider_name="openai",
                    model_id="gpt-4o",
                    prompt="What is the capital of France?",
                    reference="Paris",
                ),
            )
        finally:
            activities_mod._provider_registry = old_registry
            activities_mod._cost_calculator = old_calculator

        assert result.failed is False
        assert result.response == "The answer is 42."
        assert result.tokens_input == 1000
        assert result.tokens_output == 2000
        assert result.latency_ms >= 0

        # The real prompt reached the provider, not a fabricated placeholder.
        assert provider.call_count == 1
        assert _message_text(provider.received_messages[0]) == "What is the capital of France?"

        expected_cost = (1000 / 1_000_000 * 2.50) + (2000 / 1_000_000 * 10.00)
        assert result.cost_usd == pytest.approx(expected_cost, abs=1e-9)

    async def test_execute_item_activity_applies_template_and_system_prompt(self) -> None:
        """The activity renders the prompt template and system prompt."""
        from app.evaluation.temporal import activities as activities_mod
        from app.evaluation.temporal.activities import (
            ExecuteItemInput,
            configure_cost_calculator,
            configure_provider_registry,
        )

        provider = RecordingChatProvider()
        registry = ProviderRegistry()
        registry.register(provider)

        old_registry = activities_mod._provider_registry
        old_calculator = activities_mod._cost_calculator
        try:
            configure_provider_registry(registry)
            configure_cost_calculator(build_default_cost_calculator())

            result = await activities_mod.execute_item_activity(
                ExecuteItemInput(
                    run_id="run-2",
                    item_index=0,
                    provider_name="openai",
                    model_id="gpt-4o",
                    prompt="paris",
                    reference="Paris",
                    prompt_template="What is the capital? {prompt}",
                    system_prompt="You are a geography expert.",
                ),
            )
        finally:
            activities_mod._provider_registry = old_registry
            activities_mod._cost_calculator = old_calculator

        assert result.failed is False
        assert len(provider.received_messages) == 2
        assert provider.received_messages[0].role == MessageRole.SYSTEM
        assert _message_text(provider.received_messages[0]) == "You are a geography expert."
        assert _message_text(provider.received_messages[1]) == "What is the capital? paris"

    async def test_execute_item_activity_failure_is_captured(self) -> None:
        """Provider failures surface as a failed result with an error."""
        from app.evaluation.temporal import activities as activities_mod
        from app.evaluation.temporal.activities import (
            ExecuteItemInput,
            configure_cost_calculator,
            configure_provider_registry,
        )

        class FailingProvider(RecordingChatProvider):
            async def chat(
                self,
                messages: list[Message],
                model: str = "",
                options: Any = None,
            ) -> ChatResponse:
                msg = "Boom"
                raise RuntimeError(msg)

        registry = ProviderRegistry()
        registry.register(FailingProvider())

        old_registry = activities_mod._provider_registry
        old_calculator = activities_mod._cost_calculator
        try:
            configure_provider_registry(registry)
            configure_cost_calculator(build_default_cost_calculator())

            result = await activities_mod.execute_item_activity(
                ExecuteItemInput(
                    run_id="run-3",
                    item_index=0,
                    provider_name="openai",
                    model_id="gpt-4o",
                    prompt="Question",
                ),
            )
        finally:
            activities_mod._provider_registry = old_registry
            activities_mod._cost_calculator = old_calculator

        assert result.failed is True
        assert result.error == "Boom"
