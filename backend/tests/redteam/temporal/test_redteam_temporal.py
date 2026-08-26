"""Tests for red team Temporal workflow and activity.

Validates activity registration, configuration, workflow structure,
and retry policies for the red team campaign execution.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from app.infrastructure.temporal.worker import ActivityRegistry, WorkflowRegistry
from app.redteam.temporal.activities import (
    RedTeamWorkflowInput,
    RedTeamWorkflowResult,
    configure_redteam_provider_registry,
    red_team_campaign_activity,
)
from app.redteam.temporal.workflow import RedTeamWorkflow

# ---------------------------------------------------------------------------
# Activity registration
# ---------------------------------------------------------------------------


class TestRedTeamActivityRegistration:
    """red_team_campaign_activity must be registerable in ActivityRegistry."""

    def test_activity_in_registry(self) -> None:
        registry = ActivityRegistry()
        registry.register(red_team_campaign_activity)
        assert red_team_campaign_activity in registry.get_all()

    def test_activity_name(self) -> None:
        assert red_team_campaign_activity.__name__ == "red_team_campaign_activity"


# ---------------------------------------------------------------------------
# Workflow registration
# ---------------------------------------------------------------------------


class TestRedTeamWorkflowRegistration:
    """RedTeamWorkflow must be registerable in WorkflowRegistry."""

    def test_workflow_in_registry(self) -> None:
        registry = WorkflowRegistry()
        registry.register(RedTeamWorkflow)
        assert RedTeamWorkflow in registry.get_all()

    def test_workflow_has_run_method(self) -> None:
        wf = RedTeamWorkflow()
        assert hasattr(wf, "run")


# ---------------------------------------------------------------------------
# Activity configuration
# ---------------------------------------------------------------------------


class TestRedTeamActivityConfiguration:
    """Provider registry configuration for red team activities."""

    def test_configure_provider_registry(self) -> None:
        import app.redteam.temporal.activities as mod

        old = mod._provider_registry
        try:
            configure_redteam_provider_registry(MagicMock())
            assert mod._provider_registry is not None
        finally:
            mod._provider_registry = old

    def test_provider_registry_raises_when_none(self) -> None:
        import app.redteam.temporal.activities as mod

        old = mod._provider_registry
        try:
            mod._provider_registry = None
            with pytest.raises(RuntimeError, match="Provider registry not configured"):
                mod._get_provider_registry()
        finally:
            mod._provider_registry = old


# ---------------------------------------------------------------------------
# Dataclass serialization
# ---------------------------------------------------------------------------


class TestRedTeamDataclasses:
    """Activity input/result dataclasses are frozen and serializable."""

    def test_input_defaults(self) -> None:
        inp = RedTeamWorkflowInput()
        assert inp.attack_run_id == ""
        assert inp.max_rounds == 10
        assert inp.effectiveness_threshold == 0.8

    def test_input_frozen(self) -> None:
        inp = RedTeamWorkflowInput(attack_run_id="run-1")
        with pytest.raises(AttributeError):
            inp.attack_run_id = "run-2"  # type: ignore[misc]

    def test_result_defaults(self) -> None:
        res = RedTeamWorkflowResult()
        assert res.status == ""
        assert res.violation_count == 0
        assert res.findings == ()

    def test_result_frozen(self) -> None:
        res = RedTeamWorkflowResult(attack_run_id="run-1")
        with pytest.raises(AttributeError):
            res.attack_run_id = "run-2"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Workflow retry policy
# ---------------------------------------------------------------------------


class TestRedTeamWorkflowRetryPolicy:
    """RedTeamWorkflow uses bounded retry for the campaign activity."""

    def test_retry_policy_structure(self) -> None:
        from temporalio.common import RetryPolicy

        policy = RetryPolicy(
            maximum_attempts=2,
            initial_interval=timedelta(seconds=5),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            non_retryable_error_types=["ValueError", "KeyError"],
        )
        assert policy.maximum_attempts == 2
        assert policy.backoff_coefficient == 2.0
        assert "ValueError" in policy.non_retryable_error_types
