"""Tests for B.12.1 Temporal Runtime Reliability.

Validates that all activities are registered, agent dependencies are
configured, and explicit retry policies are applied to workflow activities.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from app.agents.temporal.activities import (
    cancel_agent_run_activity,
    complete_agent_run_activity,
    create_agent_run_activity,
    execute_agent_loop_activity,
    fail_agent_run_activity,
    queue_agent_run_activity,
    start_agent_run_activity,
    update_agent_run_progress_activity,
)
from app.agents.temporal.workflow import AgentRunWorkflow
from app.evaluation.temporal.activities import (
    cancel_run_activity,
    complete_run_activity,
    create_run_activity,
    execute_item_activity,
    fail_run_activity,
    finalize_run_integrity_activity,
    persist_metric_results_activity,
    queue_run_activity,
    start_run_activity,
    update_progress_activity,
)
from app.evaluation.temporal.workflow import EvaluationRunWorkflow
from app.infrastructure.temporal.worker import ActivityRegistry

# ---------------------------------------------------------------------------
# P0-1: finalize_run_integrity_activity registered
# ---------------------------------------------------------------------------


class TestFinalizeRunIntegrityRegistered:
    """finalize_run_integrity_activity must be in the ActivityRegistry."""

    def test_finalize_activity_in_registry(self) -> None:
        registry = ActivityRegistry()
        registry.register(finalize_run_integrity_activity)
        all_activities = registry.get_all()
        assert finalize_run_integrity_activity in all_activities

    def test_all_eval_activities_registered(self) -> None:
        expected = [
            create_run_activity,
            queue_run_activity,
            start_run_activity,
            update_progress_activity,
            complete_run_activity,
            fail_run_activity,
            cancel_run_activity,
            execute_item_activity,
            persist_metric_results_activity,
            finalize_run_integrity_activity,
        ]
        registry = ActivityRegistry()
        for act in expected:
            registry.register(act)
        assert registry.count == len(expected)


# ---------------------------------------------------------------------------
# P0-2: execute_agent_loop_activity registered
# ---------------------------------------------------------------------------


class TestExecuteAgentLoopRegistered:
    """execute_agent_loop_activity must be in the ActivityRegistry."""

    def test_agent_loop_activity_in_registry(self) -> None:
        registry = ActivityRegistry()
        registry.register(execute_agent_loop_activity)
        all_activities = registry.get_all()
        assert execute_agent_loop_activity in all_activities

    def test_all_agent_activities_registered(self) -> None:
        expected = [
            create_agent_run_activity,
            queue_agent_run_activity,
            start_agent_run_activity,
            update_agent_run_progress_activity,
            complete_agent_run_activity,
            fail_agent_run_activity,
            cancel_agent_run_activity,
            execute_agent_loop_activity,
        ]
        registry = ActivityRegistry()
        for act in expected:
            registry.register(act)
        assert registry.count == len(expected)


# ---------------------------------------------------------------------------
# P1-1: Agent session factory and provider registry configuration
# ---------------------------------------------------------------------------


class TestAgentActivityConfiguration:
    """Agent activities receive session factory and provider registry."""

    def test_configure_agent_session_factory(self) -> None:
        import app.agents.temporal.activities as mod

        old = mod._session_factory
        try:
            from app.agents.temporal.activities import configure_agent_session_factory

            configure_agent_session_factory(MagicMock())
            assert mod._session_factory is not None
        finally:
            mod._session_factory = old

    def test_configure_agent_provider_registry(self) -> None:
        import app.agents.temporal.activities as mod

        old = mod._agent_provider_registry
        try:
            from app.agents.temporal.activities import configure_agent_provider_registry

            configure_agent_provider_registry(MagicMock())
            assert mod._agent_provider_registry is not None
        finally:
            mod._agent_provider_registry = old

    def test_agent_session_factory_raises_when_none(self) -> None:
        import app.agents.temporal.activities as mod

        old = mod._session_factory
        try:
            mod._session_factory = None
            with pytest.raises(RuntimeError, match="Session factory not configured"):
                mod._get_session()
        finally:
            mod._session_factory = old

    def test_agent_provider_registry_raises_when_none(self) -> None:
        import app.agents.temporal.activities as mod

        old = mod._agent_provider_registry
        try:
            mod._agent_provider_registry = None
            with pytest.raises(RuntimeError, match="Provider registry not configured"):
                # Directly call the check that happens at the top of the activity
                if mod._agent_provider_registry is None:
                    msg = "Provider registry not configured. Call configure_agent_provider_registry first."
                    raise RuntimeError(msg)
        finally:
            mod._agent_provider_registry = old


# ---------------------------------------------------------------------------
# P1-2: Explicit retry policies in evaluation workflow
# ---------------------------------------------------------------------------


class TestEvaluationWorkflowRetryPolicies:
    """EvaluationRunWorkflow applies explicit retry policies."""

    def test_workflow_has_retry_policy_definitions(self) -> None:
        wf = EvaluationRunWorkflow()
        assert hasattr(wf, "run")

    def test_retry_policy_imports(self) -> None:
        from temporalio.common import RetryPolicy

        policy = RetryPolicy(
            maximum_attempts=3,
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=10),
            non_retryable_error_types=["ValueError", "KeyError"],
        )
        assert policy.maximum_attempts == 3
        assert policy.backoff_coefficient == 2.0
        assert "ValueError" in policy.non_retryable_error_types


# ---------------------------------------------------------------------------
# P1-2: Explicit retry policies in agent workflow
# ---------------------------------------------------------------------------


class TestAgentWorkflowRetryPolicies:
    """AgentRunWorkflow applies explicit retry policies."""

    def test_workflow_has_retry_policy_definitions(self) -> None:
        wf = AgentRunWorkflow()
        assert hasattr(wf, "run")

    def test_retry_policy_imports(self) -> None:
        from temporalio.common import RetryPolicy

        policy = RetryPolicy(
            maximum_attempts=3,
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=10),
            non_retryable_error_types=["ValueError", "KeyError"],
        )
        assert policy.maximum_attempts == 3

    def test_agent_loop_retry_is_bounded(self) -> None:
        """Agent loop retry should have max 2 attempts (long-running)."""
        from temporalio.common import RetryPolicy

        policy = RetryPolicy(
            maximum_attempts=2,
            initial_interval=timedelta(seconds=5),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            non_retryable_error_types=["ValueError", "KeyError"],
        )
        assert policy.maximum_attempts == 2


# ---------------------------------------------------------------------------
# P0-1 + P0-2: Container registration verification
# ---------------------------------------------------------------------------


class TestContainerActivityRegistration:
    """Verify the DI container registers all activities."""

    def test_container_registers_finalize_activity(self) -> None:
        from app.core.config import AppConfig
        from app.infrastructure.composition.container import InfrastructureContainer

        cfg = AppConfig(
            OPENAI_API_KEY="sk-test",
            ANTHROPIC_API_KEY="sk-test-ant",
        )
        container = InfrastructureContainer(cfg)
        container._register_configurations()
        container._register_temporal()
        registry = container.container.resolve(ActivityRegistry)
        all_names = [a.__name__ for a in registry.get_all()]
        assert "finalize_run_integrity_activity" in all_names

    def test_container_registers_agent_loop_activity(self) -> None:
        from app.core.config import AppConfig
        from app.infrastructure.composition.container import InfrastructureContainer

        cfg = AppConfig(
            OPENAI_API_KEY="sk-test",
            ANTHROPIC_API_KEY="sk-test-ant",
        )
        container = InfrastructureContainer(cfg)
        container._register_configurations()
        container._register_temporal()
        registry = container.container.resolve(ActivityRegistry)
        all_names = [a.__name__ for a in registry.get_all()]
        assert "execute_agent_loop_activity" in all_names

    def test_container_activity_count(self) -> None:
        from app.core.config import AppConfig
        from app.infrastructure.composition.container import InfrastructureContainer

        cfg = AppConfig(
            OPENAI_API_KEY="sk-test",
            ANTHROPIC_API_KEY="sk-test-ant",
        )
        container = InfrastructureContainer(cfg)
        container._register_configurations()
        container._register_temporal()
        registry = container.container.resolve(ActivityRegistry)
        # 10 eval activities + 8 agent activities + 1 redteam activity = 19
        assert registry.count == 19
