"""Tests for the context module."""

from __future__ import annotations

import pytest

from app.evaluation.execution.context.context import (
    CancellationToken,
    ExecutionContext,
    MetricSelection,
    PipelineContext,
    ProviderSelection,
    TraceIdentifiers,
)
from app.evaluation.execution.pipeline.plan import ExecutionPlan
from app.kernel.entities.base import UUIDv7


class TestCancellationToken:
    """Tests for CancellationToken."""

    def test_default_not_cancelled(self) -> None:
        """Verify default is not cancelled."""
        token = CancellationToken()
        assert not token.is_cancelled
        assert not token.is_force_cancelled

    def test_cancel(self) -> None:
        """Verify cancel creates a cancelled token."""
        token = CancellationToken()
        cancelled = token.cancel()
        assert cancelled.is_cancelled
        assert not cancelled.is_force_cancelled

    def test_force_cancel(self) -> None:
        """Verify force cancel creates a force-cancelled token."""
        token = CancellationToken()
        cancelled = token.cancel(force=True)
        assert cancelled.is_cancelled
        assert cancelled.is_force_cancelled

    def test_immutability(self) -> None:
        """Verify CancellationToken is frozen."""
        token = CancellationToken()
        with pytest.raises(AttributeError):
            token.cancelled = True  # type: ignore[misc]


class TestTraceIdentifiers:
    """Tests for TraceIdentifiers."""

    def test_from_correlation_id(self) -> None:
        """Verify from_correlation_id sets all relevant fields."""
        trace = TraceIdentifiers.from_correlation_id("corr-123")
        assert trace.trace_id == "corr-123"
        assert trace.correlation_id == "corr-123"

    def test_empty_defaults(self) -> None:
        """Verify defaults are empty strings."""
        trace = TraceIdentifiers()
        assert trace.trace_id == ""
        assert trace.correlation_id == ""
        assert trace.causation_id == ""
        assert trace.span_id == ""


class TestProviderSelection:
    """Tests for ProviderSelection."""

    def test_defaults(self) -> None:
        """Verify default values."""
        sel = ProviderSelection()
        assert sel.provider_name == ""
        assert sel.model_id == ""
        assert sel.strategy_name == "default"

    def test_custom_values(self) -> None:
        """Verify custom values are preserved."""
        sel = ProviderSelection(
            provider_name="openai",
            model_id="gpt-4",
            strategy_name="round-robin",
        )
        assert sel.provider_name == "openai"
        assert sel.model_id == "gpt-4"
        assert sel.strategy_name == "round-robin"


class TestMetricSelection:
    """Tests for MetricSelection."""

    def test_defaults(self) -> None:
        """Verify default values."""
        sel = MetricSelection()
        assert sel.metric_names == ()
        assert sel.config == {}

    def test_custom_values(self) -> None:
        """Verify custom values are preserved."""
        sel = MetricSelection(
            metric_names=("accuracy", "relevance"),
            config={"accuracy": "exact_match"},
        )
        assert sel.metric_names == ("accuracy", "relevance")
        assert sel.config == {"accuracy": "exact_match"}


class TestExecutionContext:
    """Tests for ExecutionContext."""

    def test_empty_defaults(self) -> None:
        """Verify all fields are None by default."""
        ctx = ExecutionContext()
        assert ctx.budget is None
        assert ctx.limits is None
        assert ctx.policy is None
        assert ctx.priority_value == "normal"


class TestPipelineContext:
    """Tests for PipelineContext."""

    def test_default_creation(self) -> None:
        """Verify context can be created with defaults."""
        ctx = PipelineContext()
        assert ctx.run_id is not None
        assert not ctx.is_cancelled
        assert not ctx.is_force_cancelled

    def test_cancellation(self) -> None:
        """Verify with_cancellation returns a new context."""
        ctx = PipelineContext()
        cancelled_ctx = ctx.with_cancellation()
        assert not ctx.is_cancelled  # Original unchanged
        assert cancelled_ctx.is_cancelled

    def test_force_cancellation(self) -> None:
        """Verify force cancellation."""
        ctx = PipelineContext()
        cancelled_ctx = ctx.with_cancellation(force=True)
        assert cancelled_ctx.is_force_cancelled

    def test_immutability(self) -> None:
        """Verify PipelineContext is frozen."""
        ctx = PipelineContext()
        with pytest.raises(AttributeError):
            ctx.run_id = UUIDv7.generate()  # type: ignore[misc]

    def test_with_plan(self) -> None:
        """Verify context can hold a plan reference."""
        plan = ExecutionPlan.create(run_id=UUIDv7.generate())
        ctx = PipelineContext(plan=plan)
        assert ctx.plan is not None
        assert ctx.plan.run_id == plan.run_id
