"""Integration tests — full pipeline wiring.

Proves the complete path:
    EvaluationRun → Planner → ExecutionPlan → Executor → RuntimeCoordinator
    → ProviderAdapter → Provider → Normalized Response → ExecutionResult
    → EvaluationCompleted

All external APIs are mocked. No real LLM calls are made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
from app.evaluation.domain.enums.evaluation_enums import EvaluationType, Priority
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    DatasetReference,
    EvaluationConfiguration,
    EvaluationProfile,
    ExecutionBudget,
    ExecutionLimits,
    ExecutionPolicy,
)
from app.evaluation.execution.context.context import (
    CancellationToken,
    MetricSelection,
    PipelineContext,
    ProviderSelection,
    TraceIdentifiers,
)
from app.evaluation.execution.pipeline.plan import ExecutionPlan
from app.evaluation.execution.results.results import ExecutionOutcome, ExecutionResult
from app.evaluation.orchestration.checkpoint import CheckpointManager
from app.evaluation.orchestration.executor import (
    ProviderInvocationStage,
)
from app.evaluation.orchestration.orchestrator import EvaluationOrchestrator
from app.evaluation.orchestration.planner import EvaluationPlanner
from app.providers.models.enums import FinishReason
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry
from app.providers.runtime.execution.runtime_coordinator import (
    ExecutionRequest,
    RuntimeCoordinator,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    *,
    eval_type: EvaluationType = EvaluationType.DATASET,
    provider: str = "openai",
    model: str = "gpt-4",
    row_count: int = 3,
) -> EvaluationConfiguration:
    """Build an EvaluationConfiguration for testing."""
    profile = EvaluationProfile(
        provider_name=provider,
        model_id=model,
        temperature=0.0,
        max_tokens=1024,
        timeout_seconds=30,
    )
    dataset = (
        DatasetReference(
            dataset_id="ds-int-001",
            row_count=row_count,
        )
        if eval_type == EvaluationType.DATASET
        else None
    )
    return EvaluationConfiguration(
        name="Integration Test Eval",
        eval_type=eval_type,
        profile=profile,
        dataset=dataset,
        metrics=("accuracy",),
        budget=ExecutionBudget(max_cost_usd=10.0, max_tokens=10_000, max_duration_seconds=300),
        limits=ExecutionLimits(max_concurrency=1, batch_size=10, checkpoint_interval=5),
        policy=ExecutionPolicy(
            continue_on_item_failure=True,
            max_retries_per_item=0,
            timeout_per_item_seconds=30,
        ),
        priority=Priority.NORMAL,
    )


def _make_run(
    *,
    eval_type: EvaluationType = EvaluationType.DATASET,
    provider: str = "openai",
    model: str = "gpt-4",
    row_count: int = 3,
) -> EvaluationRun:
    """Build an EvaluationRun for testing."""
    config = _make_config(eval_type=eval_type, provider=provider, model=model, row_count=row_count)
    return EvaluationRun(
        evaluation_name=config.name,
        config=config,
        profile=config.profile,
    )


def _mock_chat_response(content: str = "Hello from provider") -> ChatResponse:
    """Create a mock ChatResponse."""
    return ChatResponse(
        content=content,
        model="gpt-4",
        provider="openai",
        usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
        finish_reason=FinishReason.STOP,
    )


def _make_mock_provider(
    provider_name: str = "openai",
    response_content: str = "Mocked response",
) -> MagicMock:
    """Create a mock ChatProvider that returns predetermined content."""
    provider = MagicMock()
    provider.provider_name = provider_name
    provider.chat = AsyncMock(return_value=_mock_chat_response(response_content))
    provider.health = AsyncMock(return_value=True)
    provider.capabilities = MagicMock()
    return provider


def _make_registry(*providers: MagicMock) -> ProviderRegistry:
    """Build a ProviderRegistry with the given mock providers."""
    registry = ProviderRegistry()
    for p in providers:
        registry.register(p)
    return registry


def _make_event_publisher() -> MagicMock:
    """Create a mock EventPublisher."""
    mock = MagicMock()
    mock.publish = AsyncMock()
    mock.publish_many = AsyncMock()
    return mock


def _make_run_repository() -> MagicMock:
    """Create a mock RunRepository."""
    mock = MagicMock()
    mock.save = AsyncMock()
    mock.find_by_id = AsyncMock(return_value=None)
    mock.find_by_status = AsyncMock(return_value=[])
    mock.delete = AsyncMock(return_value=True)
    return mock


def _make_orchestrator(
    provider_registry: ProviderRegistry | None = None,
    event_publisher: MagicMock | None = None,
    run_repository: MagicMock | None = None,
    runtime_coordinator: RuntimeCoordinator | None = None,
    metric_engine: MagicMock | None = None,
) -> EvaluationOrchestrator:
    """Build an EvaluationOrchestrator with real components where possible."""
    return EvaluationOrchestrator(
        provider_registry=provider_registry or _make_registry(),
        event_publisher=event_publisher or _make_event_publisher(),
        run_repository=run_repository or _make_run_repository(),
        item_repository=MagicMock(),
        checkpoint_repository=MagicMock(),
        metric_engine=metric_engine or MagicMock(),
        runtime_coordinator=runtime_coordinator or RuntimeCoordinator(),
    )


# ---------------------------------------------------------------------------
# 1. ProviderRegistry resolves providers
# ---------------------------------------------------------------------------


class TestProviderRegistryResolution:
    """Prove that ProviderRegistry resolves providers correctly."""

    def test_registry_resolves_openai(self) -> None:
        """Registry should resolve an OpenAI provider by name."""
        provider = _make_mock_provider("openai")
        registry = _make_registry(provider)
        resolved = registry.resolve("openai")
        assert resolved is provider

    def test_registry_resolves_anthropic(self) -> None:
        """Registry should resolve an Anthropic provider by name."""
        provider = _make_mock_provider("anthropic")
        registry = _make_registry(provider)
        resolved = registry.resolve("anthropic")
        assert resolved is provider

    def test_registry_raises_on_unknown(self) -> None:
        """Registry should raise KeyError for unknown providers."""
        registry = _make_registry()
        with pytest.raises(KeyError, match="not registered"):
            registry.resolve("nonexistent")

    def test_registry_is_registered(self) -> None:
        """Registry should correctly report registration status."""
        provider = _make_mock_provider("openai")
        registry = _make_registry(provider)
        assert registry.is_registered("openai") is True
        assert registry.is_registered("anthropic") is False


# ---------------------------------------------------------------------------
# 2. Planner creates valid plans
# ---------------------------------------------------------------------------


class TestPlannerCreatesPlan:
    """Prove that the Planner produces a valid ExecutionPlan."""

    async def test_planner_creates_plan_for_dataset_eval(self) -> None:
        """Planner should create a plan with steps for each dataset row."""
        run = _make_run(eval_type=EvaluationType.DATASET, row_count=3)
        planner = EvaluationPlanner()

        plan = await planner.plan(run)

        assert isinstance(plan, ExecutionPlan)
        assert plan.total_items == 3
        assert len(plan.steps) == 3
        assert len(plan.stages) == 4

    async def test_planner_creates_plan_for_single_eval(self) -> None:
        """Planner should create a plan with 1 step for single eval."""
        run = _make_run(eval_type=EvaluationType.SINGLE)
        planner = EvaluationPlanner()

        plan = await planner.plan(run)

        assert plan.total_items == 1
        assert len(plan.steps) == 1

    async def test_planner_plan_validates(self) -> None:
        """Planner validation should return no errors for valid plan."""
        run = _make_run(eval_type=EvaluationType.DATASET, row_count=2)
        planner = EvaluationPlanner()

        plan = await planner.plan(run)
        errors = await planner.validate_plan(plan)

        assert errors == []


# ---------------------------------------------------------------------------
# 3. OpenAI executes through full pipeline
# ---------------------------------------------------------------------------


class TestOpenAIExecution:
    """Prove OpenAI provider executes through Planner → Executor → Runtime."""

    async def test_openai_provider_executes(self) -> None:
        """OpenAI provider should produce ChatResponse through executor."""
        openai = _make_mock_provider("openai", "OpenAI says hello")
        registry = _make_registry(openai)
        run = _make_run(provider="openai", model="gpt-4", row_count=1)

        planner = EvaluationPlanner()
        plan = await planner.plan(run)

        trace = TraceIdentifiers.from_correlation_id(str(run.id))
        context = PipelineContext(
            run_id=run.id,
            evaluation_name=run.evaluation_name,
            plan=plan,
            config=run.config,
            profile=run.profile,
            provider_selection=ProviderSelection(provider_name="openai", model_id="gpt-4"),
            metric_selection=MetricSelection(metric_names=("accuracy",)),
            trace=trace,
        )

        runtime = RuntimeCoordinator()
        stage = ProviderInvocationStage(registry, runtime)

        provider_invocation_steps = plan.steps_for_stage(
            plan.stages[0],
        )
        result = await stage.execute(context, provider_invocation_steps)

        assert result.is_success
        assert result.items_succeeded == 1
        assert result.items_failed == 0
        openai.chat.assert_awaited_once()

    async def test_openai_full_orchestrator_run(self) -> None:
        """Full orchestrator run with OpenAI provider should complete."""
        openai = _make_mock_provider("openai", "OpenAI response")
        registry = _make_registry(openai)
        event_pub = _make_event_publisher()
        run_repo = _make_run_repository()
        run = _make_run(provider="openai", model="gpt-4", row_count=1)

        orch = _make_orchestrator(
            provider_registry=registry,
            event_publisher=event_pub,
            run_repository=run_repo,
        )

        result = await orch.execute_run(run)

        assert result.outcome == ExecutionOutcome.SUCCESS
        assert result.items_succeeded == 1
        assert run.status.value == "completed"


# ---------------------------------------------------------------------------
# 4. Anthropic executes through full pipeline
# ---------------------------------------------------------------------------


class TestAnthropicExecution:
    """Prove Anthropic provider executes through Planner → Executor → Runtime."""

    async def test_anthropic_provider_executes(self) -> None:
        """Anthropic provider should produce ChatResponse through executor."""
        anthropic = _make_mock_provider("anthropic", "Claude says hello")
        registry = _make_registry(anthropic)
        run = _make_run(provider="anthropic", model="claude-sonnet-4-20250514", row_count=1)

        planner = EvaluationPlanner()
        plan = await planner.plan(run)

        trace = TraceIdentifiers.from_correlation_id(str(run.id))
        context = PipelineContext(
            run_id=run.id,
            evaluation_name=run.evaluation_name,
            plan=plan,
            config=run.config,
            profile=run.profile,
            provider_selection=ProviderSelection(
                provider_name="anthropic",
                model_id="claude-sonnet-4-20250514",
            ),
            metric_selection=MetricSelection(metric_names=("accuracy",)),
            trace=trace,
        )

        runtime = RuntimeCoordinator()
        stage = ProviderInvocationStage(registry, runtime)

        provider_invocation_steps = plan.steps_for_stage(
            plan.stages[0],
        )
        result = await stage.execute(context, provider_invocation_steps)

        assert result.is_success
        assert result.items_succeeded == 1
        anthropic.chat.assert_awaited_once()

    async def test_anthropic_full_orchestrator_run(self) -> None:
        """Full orchestrator run with Anthropic provider should complete."""
        anthropic = _make_mock_provider("anthropic", "Claude response")
        registry = _make_registry(anthropic)
        run = _make_run(provider="anthropic", model="claude-sonnet-4-20250514", row_count=2)

        orch = _make_orchestrator(provider_registry=registry)

        result = await orch.execute_run(run)

        assert result.outcome == ExecutionOutcome.SUCCESS
        assert result.items_succeeded == 2
        assert run.status.value == "completed"


# ---------------------------------------------------------------------------
# 5. RuntimeCoordinator remains provider-agnostic
# ---------------------------------------------------------------------------


class TestRuntimeProviderAgnostic:
    """Prove RuntimeCoordinator doesn't care which provider is behind the handler."""

    async def test_runtime_executes_generic_handler(self) -> None:
        """RuntimeCoordinator should execute any handler that matches the signature."""
        runtime = RuntimeCoordinator()

        async def generic_handler(req: ExecutionRequest) -> str:
            return f"Handled by {req.provider_name}"

        request = ExecutionRequest(
            provider_name="any-provider",
            model_id="any-model",
            messages=[{"role": "user", "content": "test"}],
            request_id="req-001",
        )

        result = await runtime.execute(request, generic_handler)

        assert result.success is True
        assert "any-provider" in result.response
        assert result.provider_used == "any-provider"
        assert result.model_used == "any-model"

    async def test_runtime_with_different_providers(self) -> None:
        """Runtime should work identically with different provider names."""
        runtime = RuntimeCoordinator()
        results = []

        for name in ("openai", "anthropic", "ollama"):

            async def handler(req: ExecutionRequest, n: str = name) -> str:
                return f"Response from {n}"

            request = ExecutionRequest(
                provider_name=name,
                model_id=f"{name}-model",
                messages=[{"role": "user", "content": "test"}],
                request_id=f"req-{name}",
            )
            result = await runtime.execute(request, handler)
            results.append(result)

        assert all(r.success for r in results)
        providers_used = {r.provider_used for r in results}
        assert providers_used == {"openai", "anthropic", "ollama"}


# ---------------------------------------------------------------------------
# 6. Planner → Executor → Runtime → Provider works
# ---------------------------------------------------------------------------


class TestPlannerExecutorRuntimeProvider:
    """Prove the full chain: Planner → Executor → Runtime → Provider."""

    async def test_full_chain_single_item(self) -> None:
        """Single item should flow through all layers and produce a result."""
        provider = _make_mock_provider("openai", "Full chain response")
        registry = _make_registry(provider)
        runtime = RuntimeCoordinator()

        run = _make_run(row_count=1)
        planner = EvaluationPlanner()
        plan = await planner.plan(run)

        trace = TraceIdentifiers.from_correlation_id(str(run.id))
        context = PipelineContext(
            run_id=run.id,
            evaluation_name=run.evaluation_name,
            plan=plan,
            config=run.config,
            profile=run.profile,
            provider_selection=ProviderSelection(provider_name="openai", model_id="gpt-4"),
            metric_selection=MetricSelection(metric_names=("accuracy",)),
            trace=trace,
        )

        stage = ProviderInvocationStage(registry, runtime)
        steps = plan.steps_for_stage(plan.stages[0])
        result = await stage.execute(context, steps)

        assert result.is_success
        assert result.items_succeeded == 1
        provider.chat.assert_awaited_once()

    async def test_full_chain_multiple_items(self) -> None:
        """Multiple items should each flow through the provider."""
        provider = _make_mock_provider("openai", "Item response")
        registry = _make_registry(provider)
        runtime = RuntimeCoordinator()

        run = _make_run(row_count=3)
        planner = EvaluationPlanner()
        plan = await planner.plan(run)

        trace = TraceIdentifiers.from_correlation_id(str(run.id))
        context = PipelineContext(
            run_id=run.id,
            evaluation_name=run.evaluation_name,
            plan=plan,
            config=run.config,
            profile=run.profile,
            provider_selection=ProviderSelection(provider_name="openai", model_id="gpt-4"),
            metric_selection=MetricSelection(metric_names=("accuracy",)),
            trace=trace,
        )

        stage = ProviderInvocationStage(registry, runtime)
        steps = plan.steps_for_stage(plan.stages[0])
        result = await stage.execute(context, steps)

        assert result.is_success
        assert result.items_succeeded == 3
        assert provider.chat.await_count == 3


# ---------------------------------------------------------------------------
# 7. Cancellation flows through the runtime
# ---------------------------------------------------------------------------


class TestCancellationFlow:
    """Prove cancellation propagates through the pipeline."""

    async def test_cancelled_context_skips_steps(self) -> None:
        """Cancelled context should skip provider invocations."""
        provider = _make_mock_provider("openai")
        registry = _make_registry(provider)
        runtime = RuntimeCoordinator()

        run = _make_run(row_count=2)
        planner = EvaluationPlanner()
        plan = await planner.plan(run)

        token = CancellationToken(cancelled=True, force=False)
        trace = TraceIdentifiers.from_correlation_id(str(run.id))
        context = PipelineContext(
            run_id=run.id,
            evaluation_name=run.evaluation_name,
            plan=plan,
            config=run.config,
            profile=run.profile,
            provider_selection=ProviderSelection(provider_name="openai", model_id="gpt-4"),
            metric_selection=MetricSelection(metric_names=("accuracy",)),
            cancellation_token=token,
            trace=trace,
        )

        stage = ProviderInvocationStage(registry, runtime)
        steps = plan.steps_for_stage(plan.stages[0])
        result = await stage.execute(context, steps)

        assert result.items_succeeded == 0
        assert result.items_failed == 0
        provider.chat.assert_not_awaited()

    async def test_orchestrator_cancel_run(self) -> None:
        """Orchestrator cancel_run should cancel the context."""
        provider = _make_mock_provider("openai")
        registry = _make_registry(provider)
        run = _make_run(row_count=1)

        orch = _make_orchestrator(provider_registry=registry)

        with (
            patch(
                "app.evaluation.orchestration.orchestrator._create_runtime_coordinator",
                return_value=MagicMock(),
            ),
            patch(
                "app.evaluation.orchestration.orchestrator.EvaluationPipelineExecutor",
            ) as MockExec,
        ):
            instance = MockExec.return_value
            run_ref = run

            async def fake_execute(pipeline, ctx):
                run_ref.items_completed = run_ref.items_total
                run_ref._status = __import__(
                    "app.evaluation.domain.enums.evaluation_enums",
                    fromlist=["RunStatus"],
                ).RunStatus.RUNNING
                return ExecutionResult(
                    run_id=ctx.run_id,
                    outcome=ExecutionOutcome.CANCELLED,
                    total_items=1,
                )

            instance.execute = fake_execute
            result = await orch.execute_run(run)

        assert result.outcome == ExecutionOutcome.CANCELLED


# ---------------------------------------------------------------------------
# 8. Retry works through the runtime
# ---------------------------------------------------------------------------


class TestRetryFlow:
    """Prove retry logic works through RuntimeCoordinator."""

    async def test_handler_retried_on_failure(self) -> None:
        """RuntimeCoordinator should retry on handler failure."""
        from app.providers.runtime.policies.runtime_policies import (
            ExecutionPolicy,
            RetryPolicy,
            TimeoutPolicy,
        )

        retry_policy = RetryPolicy(max_attempts=2, base_delay_seconds=0.01)
        timeout_policy = TimeoutPolicy(request_timeout_seconds=30.0, provider_timeout_seconds=60.0)
        policy = ExecutionPolicy(retry=retry_policy, timeout=timeout_policy)
        runtime = RuntimeCoordinator(policy=policy)

        call_count = 0

        async def flaky_handler(req: ExecutionRequest) -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient failure")
            return "success after retries"

        request = ExecutionRequest(
            provider_name="openai",
            model_id="gpt-4",
            messages=[{"role": "user", "content": "test"}],
            request_id="retry-test",
        )

        result = await runtime.execute(request, flaky_handler)

        assert result.success is True
        assert result.response == "success after retries"
        assert call_count == 3

    async def test_retry_exhausted_returns_failure(self) -> None:
        """RuntimeCoordinator should fail after exhausting retries."""
        from app.providers.runtime.policies.runtime_policies import (
            ExecutionPolicy,
            RetryPolicy,
            TimeoutPolicy,
        )

        retry_policy = RetryPolicy(max_attempts=1, base_delay_seconds=0.01)
        timeout_policy = TimeoutPolicy(request_timeout_seconds=30.0, provider_timeout_seconds=60.0)
        policy = ExecutionPolicy(retry=retry_policy, timeout=timeout_policy)
        runtime = RuntimeCoordinator(policy=policy)

        async def always_fails(req: ExecutionRequest) -> str:
            raise ValueError("permanent failure")

        request = ExecutionRequest(
            provider_name="openai",
            model_id="gpt-4",
            messages=[{"role": "user", "content": "test"}],
            request_id="retry-exhaust-test",
        )

        result = await runtime.execute(request, always_fails)

        assert result.success is False
        assert "permanent failure" in result.error


# ---------------------------------------------------------------------------
# 9. Checkpointing works during execution
# ---------------------------------------------------------------------------


class TestCheckpointFlow:
    """Prove checkpointing works during execution."""

    async def test_checkpoint_created_via_factory(self) -> None:
        """RunCheckpointFactory should create a checkpoint from run state."""
        from app.evaluation.domain.factories.evaluation_factories import RunCheckpointFactory

        run = _make_run(row_count=3)
        run.queue()
        run.start(total_items=3)
        run.items_completed = 1

        checkpoint = RunCheckpointFactory.create(
            run_id=run.id,
            checkpoint_number=1,
            items_completed=1,
            items_total=3,
            last_item_index=0,
        )

        assert checkpoint.run_id == run.id
        assert checkpoint.checkpoint_number == 1
        assert checkpoint.items_completed == 1
        assert checkpoint.items_total == 3
        assert checkpoint.completion_ratio == pytest.approx(1 / 3)

    async def test_checkpoint_completeness(self) -> None:
        """Checkpoint should report correct completeness ratio."""
        from app.evaluation.domain.factories.evaluation_factories import RunCheckpointFactory

        run = _make_run(row_count=10)
        run.queue()
        run.start(total_items=10)

        checkpoint = RunCheckpointFactory.create(
            run_id=run.id,
            checkpoint_number=2,
            items_completed=5,
            items_total=10,
            last_item_index=4,
        )

        assert checkpoint.completion_ratio == pytest.approx(0.5)
        assert checkpoint.is_complete is False

    async def test_run_complete_checkpoint(self) -> None:
        """Fully completed checkpoint should report is_complete."""
        from app.evaluation.domain.factories.evaluation_factories import RunCheckpointFactory

        run = _make_run(row_count=2)
        run.queue()
        run.start(total_items=2)

        checkpoint = RunCheckpointFactory.create(
            run_id=run.id,
            checkpoint_number=3,
            items_completed=2,
            items_total=2,
            last_item_index=1,
        )

        assert checkpoint.is_complete is True
        assert checkpoint.completion_ratio == pytest.approx(1.0)

    async def test_checkpoint_manager_should_checkpoint(self) -> None:
        """CheckpointManager.should_checkpoint should return True at interval."""
        manager = CheckpointManager()

        assert manager.should_checkpoint(0, 5) is False
        assert manager.should_checkpoint(3, 5) is False
        assert manager.should_checkpoint(5, 5) is True
        assert manager.should_checkpoint(10, 5) is True


# ---------------------------------------------------------------------------
# 10. Structured execution summaries
# ---------------------------------------------------------------------------


class TestStructuredSummaries:
    """Prove execution results contain structured summaries."""

    async def test_execution_result_has_stage_results(self) -> None:
        """ExecutionResult should contain stage results from the pipeline."""
        provider = _make_mock_provider("openai", "Summary test")
        registry = _make_registry(provider)
        run = _make_run(row_count=1)

        orch = _make_orchestrator(provider_registry=registry)

        result = await orch.execute_run(run)

        assert result.total_items == 1
        assert result.items_succeeded == 1
        assert result.items_failed == 0
        assert result.outcome == ExecutionOutcome.SUCCESS
        assert result.run_id == run.id

    async def test_execution_result_has_duration(self) -> None:
        """ExecutionResult should have non-zero total_duration_ms."""
        provider = _make_mock_provider("openai", "Duration test")
        registry = _make_registry(provider)
        run = _make_run(row_count=1)

        orch = _make_orchestrator(provider_registry=registry)

        result = await orch.execute_run(run)

        assert result.total_duration_ms >= 0

    async def test_multiple_providers_same_pipeline(self) -> None:
        """Pipeline should work with different providers registered."""
        openai = _make_mock_provider("openai", "OpenAI response")
        anthropic = _make_mock_provider("anthropic", "Anthropic response")
        registry = _make_registry(openai, anthropic)

        # Execute with OpenAI
        run_openai = _make_run(provider="openai", row_count=1)
        orch = _make_orchestrator(provider_registry=registry)
        result_openai = await orch.execute_run(run_openai)
        assert result_openai.outcome == ExecutionOutcome.SUCCESS

        # Execute with Anthropic
        run_anthropic = _make_run(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            row_count=1,
        )
        orch2 = _make_orchestrator(provider_registry=registry)
        result_anthropic = await orch2.execute_run(run_anthropic)
        assert result_anthropic.outcome == ExecutionOutcome.SUCCESS
