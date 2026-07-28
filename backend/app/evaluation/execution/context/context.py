"""PipelineContext — the immutable execution context for a pipeline run.

Carries all information needed by stages and steps to execute:
the evaluation run reference, execution parameters, provider/metric
selections, cancellation signals, and distributed trace identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.evaluation.execution.pipeline.plan import ExecutionPlan
from app.kernel.entities.base import UUIDv7

if TYPE_CHECKING:
    from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
    from app.evaluation.domain.value_objects.evaluation_value_objects import (
        EvaluationConfiguration,
        EvaluationMetadata,
        EvaluationProfile,
        ExecutionBudget,
        ExecutionLimits,
        ExecutionPolicy,
    )


@dataclass(frozen=True, slots=True)
class CancellationToken:
    """Immutable cancellation signal.

    A cancelled token signals that the pipeline should gracefully
    stop processing. When force is True, in-flight work should be
    abandoned immediately.
    """

    cancelled: bool = False
    force: bool = False

    @property
    def is_cancelled(self) -> bool:
        """Return True if cancellation has been requested."""
        return self.cancelled

    @property
    def is_force_cancelled(self) -> bool:
        """Return True if force cancellation has been requested."""
        return self.cancelled and self.force

    def cancel(self, *, force: bool = False) -> CancellationToken:
        """Return a new cancelled token.

        Args:
            force: If True, signals immediate abandonment.

        Returns:
            A new CancellationToken with cancelled=True.

        """
        return CancellationToken(cancelled=True, force=force)


@dataclass(frozen=True, slots=True)
class TraceIdentifiers:
    """Distributed trace identifiers for observability.

    These identifiers are passed through the execution pipeline
    to correlate log entries, metrics, and spans across stages.
    """

    trace_id: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    span_id: str = ""

    @classmethod
    def from_correlation_id(cls, correlation_id: str) -> TraceIdentifiers:
        """Create trace identifiers from a correlation ID.

        Args:
            correlation_id: The root correlation identifier.

        Returns:
            TraceIdentifiers with the correlation ID propagated.

        """
        return cls(
            trace_id=correlation_id,
            correlation_id=correlation_id,
        )


@dataclass(frozen=True, slots=True)
class ProviderSelection:
    """Reference to a provider selection (not the provider itself).

    This is a pure domain object — it references provider and model
    by name/ID rather than holding any infrastructure connection.
    """

    provider_name: str = ""
    model_id: str = ""
    strategy_name: str = "default"


@dataclass(frozen=True, slots=True)
class MetricSelection:
    """Reference to metric selections (not the metric implementations).

    Holds the metric names and any per-metric configuration.
    """

    metric_names: tuple[str, ...] = ()
    config: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Flattened execution parameters derived from configuration.

    This context is created once from the EvaluationConfiguration
    and remains immutable throughout pipeline execution.
    """

    budget: ExecutionBudget | None = None
    limits: ExecutionLimits | None = None
    policy: ExecutionPolicy | None = None
    priority_value: str = "normal"


@dataclass(frozen=True, slots=True)
class PipelineContext:
    """Immutable context for a single pipeline execution.

    The context contains all information that stages and steps
    need to execute. It is created once by the PipelineBuilder
    and read-only for the duration of pipeline execution.
    """

    # ── run reference ──────────────────────────────────────────
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    evaluation_name: str = ""
    plan: ExecutionPlan | None = None

    # ── evaluation configuration ───────────────────────────────
    config: EvaluationConfiguration | None = None
    profile: EvaluationProfile | None = None
    metadata: EvaluationMetadata | None = None

    # ── resolved execution parameters ──────────────────────────
    execution_context: ExecutionContext = field(default_factory=ExecutionContext)

    # ── reference selections (not concrete implementations) ────
    provider_selection: ProviderSelection = field(default_factory=ProviderSelection)
    metric_selection: MetricSelection = field(default_factory=MetricSelection)

    # ── execution control ──────────────────────────────────────
    cancellation_token: CancellationToken = field(default_factory=CancellationToken)

    # ── observability ──────────────────────────────────────────
    trace: TraceIdentifiers = field(default_factory=TraceIdentifiers)

    # ── helpers ────────────────────────────────────────────────

    @property
    def is_cancelled(self) -> bool:
        """Return True if cancellation has been requested."""
        return self.cancellation_token.is_cancelled

    @property
    def is_force_cancelled(self) -> bool:
        """Return True if force cancellation has been requested."""
        return self.cancellation_token.is_force_cancelled

    def with_cancellation(self, *, force: bool = False) -> PipelineContext:
        """Return a new context with cancellation set.

        Args:
            force: If True, signals immediate abandonment.

        Returns:
            A new PipelineContext with the cancellation token set.

        """
        return PipelineContext(
            run_id=self.run_id,
            evaluation_name=self.evaluation_name,
            plan=self.plan,
            config=self.config,
            profile=self.profile,
            metadata=self.metadata,
            execution_context=self.execution_context,
            provider_selection=self.provider_selection,
            metric_selection=self.metric_selection,
            cancellation_token=self.cancellation_token.cancel(force=force),
            trace=self.trace,
        )

    @classmethod
    def from_run(
        cls,
        run: EvaluationRun,
        *,
        plan: ExecutionPlan | None = None,
        trace: TraceIdentifiers | None = None,
    ) -> PipelineContext:
        """Create a pipeline context from an evaluation run.

        Args:
            run: The evaluation run to derive context from.
            plan: Optional execution plan.
            trace: Optional trace identifiers.

        Returns:
            A new PipelineContext initialised from the run.

        """
        return cls(
            run_id=run.id,
            evaluation_name=run.evaluation_name,
            plan=plan,
            config=run.config,
            profile=run.profile,
            metadata=run.metadata,
            execution_context=ExecutionContext(
                budget=run.config.budget,
                limits=run.config.limits,
                policy=run.config.policy,
                priority_value=run.priority.value,
            ),
            provider_selection=ProviderSelection(
                provider_name=run.profile.provider_name,
                model_id=run.profile.model_id,
            ),
            metric_selection=MetricSelection(
                metric_names=run.config.metrics,
            ),
            trace=trace or TraceIdentifiers(),
        )
