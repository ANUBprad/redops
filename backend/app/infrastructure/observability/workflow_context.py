"""Workflow context management for Temporal workflow observability.

Provides context variable management for propagating workflow
metadata (workflow ID, run ID, workflow type) through the
execution context for structured logging enrichment.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

WorkflowContext = dict[str, Any]

WORKFLOW_CTX: ContextVar[WorkflowContext | None] = ContextVar(
    "workflow_context",
    default=None,
)


def get_workflow_context() -> WorkflowContext | None:
    """Return the current workflow context.

    Returns:
        A dictionary with workflow metadata, or None if not in a workflow.

    """
    return WORKFLOW_CTX.get()


def set_workflow_context(workflow_id: str, run_id: str, workflow_type: str) -> WorkflowContext:
    """Set the workflow context for the current execution scope.

    Args:
        workflow_id: The Temporal workflow ID.
        run_id: The Temporal run ID.
        workflow_type: The workflow type name.

    Returns:
        The workflow context dictionary that was set.

    """
    ctx: WorkflowContext = {
        "workflow_id": workflow_id,
        "run_id": run_id,
        "workflow_type": workflow_type,
    }
    WORKFLOW_CTX.set(ctx)
    return ctx


def clear_workflow_context() -> None:
    """Clear the current workflow context."""
    WORKFLOW_CTX.set(None)
