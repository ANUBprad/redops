"""Domain enums for the Agent Runtime engine.

Re-exports shared enums from ai.core for backward compatibility.
All agent enums are now aliases of the unified AI execution enums.
"""

from __future__ import annotations

from app.ai.core.enums import CancellationReason as AgentCancellationReason
from app.ai.core.enums import FailureReason as AgentRunFailureReason
from app.ai.core.enums import Priority as AgentRunPriority
from app.ai.core.enums import RunStatus as AgentRunStatus
from app.ai.core.enums import StepStatus as StepStatus

__all__ = [
    "AgentCancellationReason",
    "AgentRunFailureReason",
    "AgentRunPriority",
    "AgentRunStatus",
    "StepStatus",
]
