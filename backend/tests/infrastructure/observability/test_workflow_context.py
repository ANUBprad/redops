"""Tests for workflow context management."""

from __future__ import annotations

from app.infrastructure.observability.workflow_context import (
    clear_workflow_context,
    get_workflow_context,
    set_workflow_context,
)


class TestWorkflowContext:
    def teardown_method(self) -> None:
        clear_workflow_context()

    def test_default_is_none(self) -> None:
        assert get_workflow_context() is None

    def test_set_and_get(self) -> None:
        ctx = set_workflow_context(
            workflow_id="wf-123",
            run_id="run-456",
            workflow_type="MyWorkflow",
        )
        assert ctx == {
            "workflow_id": "wf-123",
            "run_id": "run-456",
            "workflow_type": "MyWorkflow",
        }

        retrieved = get_workflow_context()
        assert retrieved == ctx

    def test_clear(self) -> None:
        set_workflow_context("wf-1", "run-1", "TestWorkflow")
        clear_workflow_context()
        assert get_workflow_context() is None
