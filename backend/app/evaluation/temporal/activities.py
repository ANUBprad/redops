"""Temporal activities for evaluation run execution.

Activities call the existing application handlers, ensuring no
duplicate business logic. Each activity creates its own database
session via the configured session factory.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclasses_field
from typing import TYPE_CHECKING, Any

from temporalio import activity

from app.evaluation.application.run_commands import (
    CancelEvaluationRunCommand,
    CompleteEvaluationRunCommand,
    CreateEvaluationRunCommand,
    FailEvaluationRunCommand,
    QueueEvaluationRunCommand,
    StartEvaluationRunCommand,
    UpdateRunProgressCommand,
)
from app.evaluation.application.run_handlers import (
    CancelEvaluationRunHandler,
    CompleteEvaluationRunHandler,
    CreateEvaluationRunHandler,
    FailEvaluationRunHandler,
    QueueEvaluationRunHandler,
    StartEvaluationRunHandler,
    UpdateRunProgressHandler,
)
from app.infrastructure.database.repositories.evaluation_run_repository import (
    SqlAlchemyEvaluationRunRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_session_factory: async_sessionmaker[AsyncSession] | None = None
_provider_registry: Any = None
_metric_engine: Any = None
_cost_calculator: Any = None


def configure_session_factory(factory: async_sessionmaker[AsyncSession]) -> None:
    """Set the session factory for all activities.

    Called once during worker startup.
    """
    global _session_factory
    _session_factory = factory


def configure_provider_registry(registry: Any) -> None:
    """Set the provider registry for item execution activities."""
    global _provider_registry
    _provider_registry = registry


def configure_metric_engine(engine: Any) -> None:
    """Set the metric engine for item execution activities."""
    global _metric_engine
    _metric_engine = engine


def configure_cost_calculator(calculator: Any) -> None:
    """Set the cost calculator for item execution activities."""
    global _cost_calculator
    _cost_calculator = calculator


def _get_cost_calculator() -> Any:
    """Return the configured cost calculator or a default one."""
    if _cost_calculator is None:
        from app.providers.cost.defaults import build_default_cost_calculator

        return build_default_cost_calculator()
    return _cost_calculator


def _get_session() -> AsyncSession:
    """Get a new database session."""
    if _session_factory is None:
        msg = "Session factory not configured. Call configure_session_factory first."
        raise RuntimeError(msg)
    return _session_factory()


# ---------------------------------------------------------------------------
# Activity input dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CreateRunInput:
    """Input for the create_run activity."""

    evaluation_id: str | None = None
    evaluation_name: str = ""
    provider: str = ""
    model: str = ""
    metrics: tuple[str, ...] = ()
    project_id: str | None = None
    created_by: str | None = None
    tags: tuple[str, ...] = ()
    workflow_id: str | None = None


@dataclass(frozen=True, slots=True)
class RunIdInput:
    """Input for activities that only need a run ID."""

    run_id: str


@dataclass(frozen=True, slots=True)
class StartRunInput:
    """Input for the start_run activity."""

    run_id: str
    total_items: int


@dataclass(frozen=True, slots=True)
class ProgressInput:
    """Input for the update_progress activity."""

    run_id: str
    items_completed: int = 0
    items_failed: int = 0
    token_input: int = 0
    token_output: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


@dataclass(frozen=True, slots=True)
class FailRunInput:
    """Input for the fail_run activity."""

    run_id: str
    error_code: str = ""
    error_message: str = ""


@dataclass(frozen=True, slots=True)
class CancelRunInput:
    """Input for the cancel_run activity."""

    run_id: str
    reason: str = "user_cancelled"
    force: bool = False


@dataclass(frozen=True, slots=True)
class ExecuteItemInput:
    """Input for the execute_item activity.

    Attributes:
        run_id: The evaluation run identifier.
        item_index: Zero-based index of the item in the dataset.
        provider_name: Provider identifier.
        model_id: Model identifier.
        metric_names: Metrics to evaluate for this item.
        prompt: The exact item prompt to send to the provider.
        reference: Optional reference answer for the item.
        context: Optional context for the item.
        item_id: Optional stable item identifier.
        prompt_template: Optional template with ``{variable}`` placeholders.
        system_prompt: Optional system prompt for the provider call.

    """

    run_id: str
    item_index: int
    provider_name: str
    model_id: str
    metric_names: tuple[str, ...] = ()
    prompt: str = ""
    reference: str = ""
    context: str = ""
    item_id: str = ""
    prompt_template: str | None = None
    system_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class MetricResultPayload:
    """Serializable metric evaluation result.

    Transport shape between the item execution activity and the
    metric result persistence activity.
    """

    metric_name: str
    score: float = 0.0
    normalized_score: float = 0.0
    raw_output: str = ""
    reasoning: str = ""
    metadata: dict[str, Any] = dataclasses_field(default_factory=dict)
    execution_time_ms: int = 0
    error: str | None = None
    confidence: float = 0.0
    version: str = "1.0.0"
    cost_usd: float = 0.0


@dataclass(frozen=True, slots=True)
class ExecuteItemResult:
    """Result returned by execute_item activity."""

    item_index: int
    response: str = ""
    cost_usd: float = 0.0
    tokens_input: int = 0
    tokens_output: int = 0
    latency_ms: int = 0
    failed: bool = False
    error: str | None = None
    item_id: str = ""
    metrics: tuple[MetricResultPayload, ...] = ()


# ---------------------------------------------------------------------------
# Activity results
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PersistMetricResultsInput:
    """Input for the persist_metric_results activity."""

    run_id: str
    item_id: str
    results: tuple[MetricResultPayload, ...] = ()


@dataclass(frozen=True, slots=True)
class RunResult:
    """Result returned by run lifecycle activities."""

    run_id: str
    status: str
    evaluation_name: str = ""


@dataclass(frozen=True, slots=True)
class FinalizeRunIntegrityInput:
    """Input for the finalize_run_integrity activity.

    Carries trace data, provenance, fingerprint, and metric names
    needed to evaluate thresholds and persist the full evaluation record.
    """

    run_id: str
    metric_names: tuple[str, ...] = ()
    trace_data: dict[str, Any] = dataclasses_field(default_factory=dict)
    provenance: dict[str, Any] = dataclasses_field(default_factory=dict)
    fingerprint: str = ""


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


@activity.defn
async def create_run_activity(input: CreateRunInput) -> RunResult:
    """Create a new evaluation run and return its ID."""
    activity.logger.info("Creating evaluation run name=%s", input.evaluation_name)
    async with _get_session() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = CreateEvaluationRunHandler(repo)
        command = CreateEvaluationRunCommand(
            evaluation_id=input.evaluation_id,
            evaluation_name=input.evaluation_name,
            provider=input.provider,
            model=input.model,
            metrics=input.metrics,
            project_id=input.project_id,
            created_by=input.created_by,
            tags=input.tags,
            workflow_id=input.workflow_id,
        )
        run = await handler.handle(command)
        await session.commit()
    return RunResult(
        run_id=str(run.id),
        status=run.status.value,
        evaluation_name=run.evaluation_name,
    )


@activity.defn
async def queue_run_activity(input: RunIdInput) -> RunResult:
    """Transition a run to QUEUED status."""
    activity.logger.info("Queuing evaluation run run_id=%s", input.run_id)
    async with _get_session() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = QueueEvaluationRunHandler(repo)
        command = QueueEvaluationRunCommand(run_id=input.run_id)
        run = await handler.handle(command)
        await session.commit()
    return RunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def start_run_activity(input: StartRunInput) -> RunResult:
    """Transition a run to RUNNING status."""
    activity.logger.info(
        "Starting evaluation run run_id=%s total_items=%d",
        input.run_id,
        input.total_items,
    )
    async with _get_session() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = StartEvaluationRunHandler(repo)
        command = StartEvaluationRunCommand(
            run_id=input.run_id,
            total_items=input.total_items,
        )
        run = await handler.handle(command)
        await session.commit()
    return RunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def update_progress_activity(input: ProgressInput) -> RunResult:
    """Persist progress updates for a running evaluation."""
    activity.logger.debug(
        "Updating run progress run_id=%s completed=%d",
        input.run_id,
        input.items_completed,
    )
    async with _get_session() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = UpdateRunProgressHandler(repo)
        command = UpdateRunProgressCommand(
            run_id=input.run_id,
            items_completed=input.items_completed,
            items_failed=input.items_failed,
            token_input=input.token_input,
            token_output=input.token_output,
            cost_usd=input.cost_usd,
            latency_ms=input.latency_ms,
        )
        run = await handler.handle(command)
        await session.commit()
    return RunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def complete_run_activity(input: RunIdInput) -> RunResult:
    """Mark a run as completed."""
    activity.logger.info("Completing evaluation run run_id=%s", input.run_id)
    async with _get_session() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = CompleteEvaluationRunHandler(repo)
        command = CompleteEvaluationRunCommand(run_id=input.run_id)
        run = await handler.handle(command)
        await session.commit()
    return RunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def fail_run_activity(input: FailRunInput) -> RunResult:
    """Mark a run as failed."""
    activity.logger.warning(
        "Failing evaluation run run_id=%s error_code=%s",
        input.run_id,
        input.error_code,
    )
    async with _get_session() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = FailEvaluationRunHandler(repo)
        command = FailEvaluationRunCommand(
            run_id=input.run_id,
            error_code=input.error_code,
            error_message=input.error_message,
        )
        run = await handler.handle(command)
        await session.commit()
    return RunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def cancel_run_activity(input: CancelRunInput) -> RunResult:
    """Cancel a running evaluation."""
    activity.logger.info("Cancelling evaluation run run_id=%s", input.run_id)
    async with _get_session() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = CancelEvaluationRunHandler(repo)
        command = CancelEvaluationRunCommand(
            run_id=input.run_id,
            reason=input.reason,
            force=input.force,
        )
        run = await handler.handle(command)
        await session.commit()
    return RunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def execute_item_activity(input: ExecuteItemInput) -> ExecuteItemResult:
    """Execute a single evaluation item against the provider.

    Builds the real prompt for the item, invokes the configured
    chat provider through the shared provider registry, evaluates
    the requested metrics against the generated response, and
    returns a result carrying real token usage, estimated cost,
    latency, and metric scores.

    Heartbeats are sent at meaningful boundaries so Temporal can
    detect stuck activities and honour cancellation requests.
    """
    import time

    activity.logger.info(
        "Executing item run_id=%s item_index=%d provider=%s",
        input.run_id,
        input.item_index,
        input.provider_name,
    )
    start = time.monotonic()

    try:
        activity.heartbeat(f"preparing item {input.item_index}")

        from app.evaluation.data.dataset import DatasetItem
        from app.evaluation.execution.item_executor import ItemExecutor
        from app.evaluation.execution.prompt_builder import PromptTemplate
        from app.providers.registry.registry import ProviderRegistry

        registry: Any = _provider_registry if _provider_registry is not None else ProviderRegistry()
        provider = registry.resolve(input.provider_name)

        item = DatasetItem(
            prompt=input.prompt or f"Evaluate item {input.item_index}",
            reference=input.reference or None,
            context=input.context or None,
            id=input.item_id or None,
        )

        template = PromptTemplate(
            template=input.prompt_template or "{prompt}",
            system_prompt=input.system_prompt,
        )
        executor = ItemExecutor(_get_cost_calculator(), prompt_template=template)

        activity.heartbeat(f"calling provider for item {input.item_index}")

        result = await executor.execute(
            provider,
            provider_name=input.provider_name,
            model_id=input.model_id,
            item=item,
            item_index=input.item_index,
        )

        elapsed_ms = int((time.monotonic() - start) * 1000)
        item_id = input.item_id or str(input.item_index)
        metrics: tuple[MetricResultPayload, ...] = ()
        if result.is_success:
            activity.heartbeat(f"evaluating metrics for item {input.item_index}")
            metrics = await _evaluate_metrics(
                engine=_metric_engine,
                run_id=input.run_id,
                item_id=item_id,
                metric_names=input.metric_names,
                execution=result,
                judge_provider=provider,
            )

        return ExecuteItemResult(
            item_index=input.item_index,
            response=result.response,
            cost_usd=result.cost_usd,
            tokens_input=result.tokens_input,
            tokens_output=result.tokens_output,
            latency_ms=elapsed_ms,
            failed=result.failed,
            error=result.error,
            item_id=item_id,
            metrics=metrics,
        )
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return ExecuteItemResult(
            item_index=input.item_index,
            failed=True,
            error=str(exc),
            latency_ms=elapsed_ms,
        )


async def _evaluate_metrics(
    *,
    engine: Any,
    run_id: str,
    item_id: str,
    metric_names: tuple[str, ...],
    execution: Any,
    judge_provider: Any,
) -> tuple[MetricResultPayload, ...]:
    """Evaluate the selected metrics against an executed item.

    The resolved chat provider is injected as the LLM judge so
    judge-backed metrics perform a real second LLM call. When that
    provider also implements the embedding contract (e.g. OpenAI),
    it is injected for embedding-backed metrics as well; otherwise
    those metrics produce explicit error results rather than fake
    scores.
    """
    if engine is None or not metric_names:
        return ()

    from app.evaluation.metrics.domain import MetricInput

    resolved = engine.resolve_metrics(metric_names)
    if not resolved:
        activity.logger.warning(
            "No requested metrics are registered run_id=%s requested=%s",
            run_id,
            list(metric_names),
        )
        return ()

    metadata = execution.to_metric_metadata()
    embedding_provider = judge_provider if hasattr(judge_provider, "embed") else None
    metadata.update(
        {
            "run_id": run_id,
            "item_id": item_id,
            "_judge_provider": judge_provider,
            "_judge_provider_name": execution.provider_name,
            "_judge_model": execution.model_id,
            "_embedding_provider": embedding_provider,
        }
    )
    metric_input = MetricInput(
        prompt=execution.prompt,
        response=execution.response,
        reference=execution.reference or "",
        context=execution.context or "",
        metadata=metadata,
    )

    results = await engine.evaluate_batch(resolved, metric_input)
    return tuple(_to_payload(r) for r in results)


def _to_payload(result: Any) -> MetricResultPayload:
    """Convert a domain MetricResult to its serializable payload."""
    return MetricResultPayload(
        metric_name=result.metric_name,
        score=result.score,
        normalized_score=result.normalized_score,
        raw_output=result.raw_output,
        reasoning=result.reasoning,
        metadata=dict(result.metadata),
        execution_time_ms=result.execution_time_ms,
        error=result.error,
        confidence=result.confidence,
        version=result.version,
        cost_usd=result.cost_usd,
    )


@activity.defn
async def persist_metric_results_activity(input: PersistMetricResultsInput) -> int:
    """Persist metric results for a single evaluated item."""
    if not input.results:
        return 0

    from app.evaluation.metrics.domain import MetricResult
    from app.infrastructure.database.repositories.metric_result_repository import (
        SqlAlchemyMetricResultRepository,
    )

    activity.logger.info(
        "Persisting metric results run_id=%s item_id=%s count=%d",
        input.run_id,
        input.item_id,
        len(input.results),
    )

    def to_domain(payload: MetricResultPayload) -> MetricResult:
        return MetricResult(
            metric_name=payload.metric_name,
            score=payload.score,
            normalized_score=payload.normalized_score,
            raw_output=payload.raw_output,
            reasoning=payload.reasoning,
            metadata={**payload.metadata, "run_id": input.run_id, "item_id": input.item_id},
            execution_time_ms=payload.execution_time_ms,
            error=payload.error,
            confidence=payload.confidence,
            version=payload.version,
            cost_usd=payload.cost_usd,
        )

    async with _get_session() as session:
        repo = SqlAlchemyMetricResultRepository(session)
        await repo.save_many([to_domain(p) for p in input.results])
        await session.commit()
    return len(input.results)


@activity.defn
async def finalize_run_integrity_activity(
    input: FinalizeRunIntegrityInput,
) -> str:
    """Finalize evaluation run integrity: evaluate thresholds, capture provenance, persist.

    This activity runs after all items complete. It:
    1. Loads all metric results for the run
    2. Evaluates thresholds against each metric result
    3. Determines a run-level verdict (pass/fail/error)
    4. Captures environment provenance
    5. Persists trace_data, provenance, fingerprint, and verdict to the evaluation run

    Returns the determined verdict string.
    """
    from app.evaluation.metrics.domain import MetricResult
    from app.evaluation.reliability.provenance import capture_environment
    from app.infrastructure.database.repositories.metric_result_repository import (
        SqlAlchemyMetricResultRepository,
    )

    activity.logger.info(
        "Finalizing run integrity run_id=%s metric_count=%d",
        input.run_id,
        len(input.metric_names),
    )

    # 1. Capture environment provenance (I/O — git commands, platform info)
    env_snapshot = capture_environment()

    # 2. Load all metric results for this run and evaluate thresholds
    verdict = "pass"
    async with _get_session() as session:
        metric_repo = SqlAlchemyMetricResultRepository(session)
        run_repo = SqlAlchemyEvaluationRunRepository(session)

        # Load all persisted metric results for this run
        from app.kernel.entities.base import UUIDv7 as KernelUUIDv7

        run_uuid = KernelUUIDv7.from_string(input.run_id)
        all_results: list[MetricResult] = []
        for metric_name in input.metric_names:
            results = await metric_repo.find_by_run_id(
                run_id=run_uuid,
                metric_name=metric_name,
            )
            all_results.extend(results)

        # Evaluate thresholds using the metric engine definitions
        threshold_evaluations: dict[str, bool | None] = {}
        if _metric_engine is not None and all_results:
            for metric_name in input.metric_names:
                definition = _metric_engine._definitions.get(metric_name)
                if definition is None:
                    continue
                threshold = definition.default_threshold
                if threshold is None:
                    continue

                metric_results = [r for r in all_results if r.metric_name == metric_name]
                if not metric_results:
                    threshold_evaluations[metric_name] = None
                    continue

                # Evaluate threshold against aggregated mean
                successful = [r for r in metric_results if r.is_success]
                if not successful:
                    threshold_evaluations[metric_name] = None
                    verdict = "error" if verdict != "fail" else verdict
                    continue

                mean_score = sum(r.normalized_score for r in successful) / len(successful)
                passed = mean_score >= threshold
                threshold_evaluations[metric_name] = passed

                if not passed:
                    verdict = "fail"

        # If all thresholds passed but we had only errors, verdict is error
        if verdict == "pass" and all(v is None for v in threshold_evaluations.values()):
            if threshold_evaluations:
                verdict = "error"

        # 3. Build provenance dict
        provenance_data = {
            "environment": {
                "git_commit_hash": env_snapshot.git_commit_hash,
                "git_branch": env_snapshot.git_branch,
                "python_version": env_snapshot.python_version,
                "requirements_hash": env_snapshot.requirements_hash,
                "platform_info": env_snapshot.platform_info,
            },
            "metric_versions": dict.fromkeys(input.metric_names, "1.0.0"),
            "threshold_evaluations": threshold_evaluations,
        }

        # 4. Persist to evaluation run
        from app.kernel.entities.base import UUIDv7 as KernelUUIDv7

        run = await run_repo.find_by_id(KernelUUIDv7.from_string(input.run_id))
        if run is not None:
            run.verdict = verdict
            run.trace_data = input.trace_data if input.trace_data else None
            run.provenance = provenance_data
            run.fingerprint = input.fingerprint if input.fingerprint else None
            await run_repo.save(run)
            await session.commit()

    activity.logger.info(
        "Run integrity finalized run_id=%s verdict=%s",
        input.run_id,
        verdict,
    )
    return verdict
