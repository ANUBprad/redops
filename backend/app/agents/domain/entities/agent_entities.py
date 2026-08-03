"""Domain entities for the Agent Runtime engine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.agents.domain.enums.agent_enums import (
    AgentCancellationReason,
    AgentRunFailureReason,
    AgentRunPriority,
    AgentRunStatus,
    StepStatus,
)
from app.agents.domain.events.agent_events import (
    AgentCheckpointCreated,
    AgentRunCancelled,
    AgentRunCompleted,
    AgentRunFailed,
    AgentRunQueued,
    AgentRunStarted,
    AgentRunTimedOut,
)
from app.agents.domain.value_objects.agent_value_objects import (
    AgentCheckpoint,
    AgentConfiguration,
    AgentRunMetadata,
    AgentStepResult,
)
from app.kernel.entities.base import AggregateRoot, Entity, UUIDv7, VersionMixin
from app.kernel.exceptions.errors import DomainError


class AgentStep(Entity):
    """A single step within an agent run."""

    def __init__(
        self,
        run_id: UUIDv7,
        index: int,
        tool_name: str = "",
        input_data: dict[str, Any] | None = None,
        entity_id: UUIDv7 | None = None,
    ) -> None:
        super().__init__(entity_id=entity_id)
        self.run_id = run_id
        self.index = index
        self.tool_name = tool_name
        self.input_data = input_data or {}
        self._status = StepStatus.PENDING
        self._result: AgentStepResult | None = None

    @property
    def status(self) -> StepStatus:
        return self._status

    @property
    def result(self) -> AgentStepResult | None:
        return self._result

    def start(self) -> None:
        if self._status != StepStatus.PENDING:
            msg = f"Cannot start step in {self._status.value} state"
            raise InvalidAgentStepStateError(msg, current_status=self._status)
        self._status = StepStatus.RUNNING
        self.touch()

    def complete(self, result: AgentStepResult) -> None:
        if self._status != StepStatus.RUNNING:
            msg = f"Cannot complete step in {self._status.value} state"
            raise InvalidAgentStepStateError(msg, current_status=self._status)
        self._result = result
        self._status = StepStatus.COMPLETED
        self.touch()

    def fail(self, error: str, reason: AgentRunFailureReason | None = None) -> None:
        if self._status == StepStatus.COMPLETED:
            msg = "Cannot fail a completed step"
            raise InvalidAgentStepStateError(msg, current_status=self._status)
        self._result = AgentStepResult(
            step_id=str(self.id),
            step_index=self.index,
            tool_name=self.tool_name,
            success=False,
            error=error,
        )
        self._status = StepStatus.FAILED
        self.touch()

    def retry(self) -> None:
        if self._status != StepStatus.FAILED:
            msg = f"Cannot retry step in {self._status.value} state"
            raise InvalidAgentStepStateError(msg, current_status=self._status)
        self._status = StepStatus.RETRYING
        self.touch()

    def skip(self, reason: str = "") -> None:
        if self._status in _STEP_TERMINAL_STATES:
            msg = f"Cannot skip step in {self._status.value} state"
            raise InvalidAgentStepStateError(msg, current_status=self._status)
        self._status = StepStatus.SKIPPED
        self.touch()

    def cancel(self) -> None:
        if self._status in _STEP_TERMINAL_STATES:
            msg = f"Cannot cancel step in {self._status.value} state"
            raise InvalidAgentStepStateError(msg, current_status=self._status)
        self._status = StepStatus.CANCELLED
        self.touch()


_STEP_TERMINAL_STATES: frozenset[StepStatus] = frozenset(
    {
        StepStatus.COMPLETED,
        StepStatus.FAILED,
        StepStatus.SKIPPED,
        StepStatus.CANCELLED,
    }
)


class InvalidAgentStepStateError(DomainError):
    """Raised when an agent step state transition is invalid."""

    def __init__(
        self,
        message: str = "",
        *,
        current_status: StepStatus,
        trace_id: str | None = None,
    ) -> None:
        self.current_status = current_status
        super().__init__(
            message or f"Invalid agent step state: {current_status.value}",
            error_code="INVALID_AGENT_STEP_STATE",
            details={"current_status": current_status.value},
            http_status=409,
            trace_id=trace_id,
        )


class AgentRun(AggregateRoot, VersionMixin):
    """An execution instance of an agent."""

    def __init__(
        self,
        agent_name: str,
        config: AgentConfiguration,
        metadata: AgentRunMetadata | None = None,
        entity_id: UUIDv7 | None = None,
        *,
        agent_definition_id: str | None = None,
        workflow_id: str | None = None,
    ) -> None:
        super().__init__(entity_id=entity_id)
        VersionMixin.__init__(self)
        self.agent_name = agent_name
        self.config = config
        self.metadata = metadata or AgentRunMetadata()
        self.agent_definition_id = agent_definition_id
        self.workflow_id = workflow_id
        self._status = AgentRunStatus.CREATED
        self.steps_total = 0
        self.steps_completed = 0
        self.steps_failed = 0
        self.priority = AgentRunPriority.NORMAL
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.cancelled_at: datetime | None = None
        self.token_input: int = 0
        self.token_output: int = 0
        self.cost: float = 0.0
        self.average_latency_ms: int = 0
        self._checkpoint: AgentCheckpoint | None = None
        self._failure_summary: AgentRunFailureReason | None = None
        self._cancellation_reason: AgentCancellationReason | None = None

    @property
    def status(self) -> AgentRunStatus:
        return self._status

    @property
    def checkpoint(self) -> AgentCheckpoint | None:
        return self._checkpoint

    @property
    def failure_summary(self) -> AgentRunFailureReason | None:
        return self._failure_summary

    @property
    def cancellation_reason(self) -> AgentCancellationReason | None:
        return self._cancellation_reason

    @property
    def duration_ms(self) -> int:
        if self.started_at is None:
            return 0
        end = self.completed_at or datetime.now(UTC)
        delta = end - self.started_at
        return int(delta.total_seconds() * 1000)

    @property
    def progress(self) -> float:
        if self.steps_total == 0:
            return 0.0
        return (self.steps_completed / self.steps_total) * 100.0

    @property
    def total_tokens(self) -> int:
        return self.token_input + self.token_output

    def _transition_to(self, target: AgentRunStatus) -> bool:
        """Simple state transition check."""
        if not self._can_transition_to(target):
            return False
        self._status = target
        self.touch()
        self.increment_version()
        return True

    def _can_transition_to(self, target: AgentRunStatus) -> bool:
        """Check if transition is valid."""
        return _VALID_TRANSITIONS.get(self._status, frozenset()).__contains__(target)

    def queue(self) -> None:
        if not self._transition_to(AgentRunStatus.QUEUED):
            msg = f"Cannot queue agent run from {self._status.value}"
            raise AgentRunTransitionError(msg, current_status=self._status)
        self.raise_event(
            AgentRunQueued(
                correlation_id=str(self.id),
                run_id=self.id,
                agent_name=self.agent_name,
                priority=self.priority.value,
            ),
        )

    def start(self, total_steps: int) -> None:
        if total_steps < 0:
            msg = "Total steps cannot be negative"
            raise ValueError(msg)
        self.steps_total = total_steps
        if not self._transition_to(AgentRunStatus.STARTING):
            msg = f"Cannot start agent run from {self._status.value}"
            raise AgentRunTransitionError(msg, current_status=self._status)
        if not self._transition_to(AgentRunStatus.RUNNING):
            msg = "Cannot transition agent run to RUNNING"
            raise AgentRunTransitionError(msg, current_status=self._status)
        self.started_at = datetime.now(UTC)
        self.raise_event(
            AgentRunStarted(
                correlation_id=str(self.id),
                run_id=self.id,
                provider_name=self.config.profile.provider_name,
                model_id=self.config.profile.model_id,
                total_steps=total_steps,
            ),
        )

    def complete(self) -> None:
        if not self._transition_to(AgentRunStatus.COMPLETED):
            msg = f"Cannot complete agent run from {self._status.value}"
            raise AgentRunTransitionError(msg, current_status=self._status)
        self.completed_at = datetime.now(UTC)
        self.raise_event(
            AgentRunCompleted(
                correlation_id=str(self.id),
                run_id=self.id,
                steps_completed=self.steps_completed,
                steps_total=self.steps_total,
                duration_ms=self.duration_ms,
            ),
        )

    def fail(
        self,
        error_code: str = "",
        error_message: str = "",
    ) -> None:
        if not self._transition_to(AgentRunStatus.FAILED):
            msg = f"Cannot fail agent run from {self._status.value}"
            raise AgentRunTransitionError(msg, current_status=self._status)
        self.completed_at = datetime.now(UTC)
        self._failure_summary = AgentRunFailureReason.INTERNAL_ERROR
        for reason in AgentRunFailureReason:
            if reason.value == error_code:
                self._failure_summary = reason
                break
        self.raise_event(
            AgentRunFailed(
                correlation_id=str(self.id),
                run_id=self.id,
                error_code=error_code,
                error_message=error_message,
                steps_completed=self.steps_completed,
                steps_total=self.steps_total,
            ),
        )

    def timeout(self) -> None:
        if not self._transition_to(AgentRunStatus.TIMEDOUT):
            msg = f"Cannot timeout agent run from {self._status.value}"
            raise AgentRunTransitionError(msg, current_status=self._status)
        self.completed_at = datetime.now(UTC)
        self.raise_event(
            AgentRunTimedOut(
                correlation_id=str(self.id),
                run_id=self.id,
                timeout_seconds=self.config.timeout_seconds,
                steps_completed=self.steps_completed,
                steps_total=self.steps_total,
            ),
        )

    def cancel(
        self,
        reason: AgentCancellationReason = AgentCancellationReason.USER_CANCELLED,
        *,
        force: bool = False,
    ) -> None:
        self._cancellation_reason = reason
        target = AgentRunStatus.CANCELLED if force else AgentRunStatus.CANCELLING
        if not self._transition_to(target):
            msg = f"Cannot cancel agent run from {self._status.value}"
            raise AgentRunTransitionError(msg, current_status=self._status)
        if force:
            self.completed_at = datetime.now(UTC)
        self.cancelled_at = datetime.now(UTC)
        self.raise_event(
            AgentRunCancelled(
                correlation_id=str(self.id),
                run_id=self.id,
                reason=reason,
                force=force,
                steps_completed=self.steps_completed,
                steps_total=self.steps_total,
            ),
        )

    def record_step_success(self) -> None:
        self.steps_completed += 1
        self.touch()

    def record_step_failure(self) -> None:
        self.steps_failed += 1
        self.steps_completed += 1
        self.touch()

    def record_token_usage(self, input_tokens: int, output_tokens: int) -> None:
        self.token_input += input_tokens
        self.token_output += output_tokens
        self.touch()

    def record_cost(self, cost_usd: float) -> None:
        self.cost += cost_usd
        self.touch()

    def record_latency(self, latency_ms: int) -> None:
        completed = self.steps_completed
        if completed <= 0:
            self.average_latency_ms = latency_ms
        else:
            total = self.average_latency_ms * completed + latency_ms
            self.average_latency_ms = total // (completed + 1)
        self.touch()

    def save_checkpoint(self, checkpoint: AgentCheckpoint) -> None:
        self._checkpoint = checkpoint
        self.raise_event(
            AgentCheckpointCreated(
                correlation_id=str(self.id),
                run_id=self.id,
                checkpoint_number=checkpoint.checkpoint_number,
                steps_completed=self.steps_completed,
            ),
        )

    def can_transition_to(self, target: AgentRunStatus) -> bool:
        return self._can_transition_to(target)


class AgentRunTransitionError(DomainError):
    """Raised when an agent run state transition is invalid."""

    def __init__(
        self,
        message: str = "",
        *,
        current_status: AgentRunStatus,
        trace_id: str | None = None,
    ) -> None:
        self.current_status = current_status
        super().__init__(
            message or f"Invalid agent run state: {current_status.value}",
            error_code="INVALID_AGENT_RUN_STATE",
            details={"current_status": current_status.value},
            http_status=409,
            trace_id=trace_id,
        )


_VALID_TRANSITIONS: dict[AgentRunStatus, frozenset[AgentRunStatus]] = {
    AgentRunStatus.CREATED: frozenset({AgentRunStatus.QUEUED}),
    AgentRunStatus.QUEUED: frozenset({AgentRunStatus.STARTING, AgentRunStatus.CANCELLED}),
    AgentRunStatus.STARTING: frozenset(
        {AgentRunStatus.RUNNING, AgentRunStatus.FAILED, AgentRunStatus.CANCELLED}
    ),
    AgentRunStatus.RUNNING: frozenset(
        {
            AgentRunStatus.COMPLETED,
            AgentRunStatus.FAILED,
            AgentRunStatus.PAUSED,
            AgentRunStatus.TIMEDOUT,
            AgentRunStatus.CANCELLING,
            AgentRunStatus.CANCELLED,
        }
    ),
    AgentRunStatus.PAUSED: frozenset({AgentRunStatus.RUNNING, AgentRunStatus.CANCELLED}),
    AgentRunStatus.CANCELLING: frozenset({AgentRunStatus.CANCELLED}),
}
