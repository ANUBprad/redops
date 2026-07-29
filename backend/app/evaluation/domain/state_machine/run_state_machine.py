"""Evaluation run state machine."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.evaluation.domain.enums.evaluation_enums import RunStatus
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import DomainError


class InvalidTransitionError(DomainError):
    """Raised when a state transition is not allowed."""

    def __init__(
        self,
        message: str = "",
        *,
        current_status: RunStatus,
        target_status: RunStatus,
        trace_id: str | None = None,
    ) -> None:
        """Initialize InvalidTransitionError.

        Args:
            message: Error description.
            current_status: Current run status.
            target_status: Target run status.
            trace_id: Optional trace ID.

        """
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            message or f"Cannot transition from {current_status.value} to {target_status.value}",
            error_code="INVALID_TRANSITION",
            details={
                "current_status": current_status.value,
                "target_status": target_status.value,
            },
            http_status=409,
            trace_id=trace_id,
        )


@dataclass(frozen=True, slots=True)
class TransitionContext:
    """Context passed to guard conditions during transition evaluation."""

    run_id: UUIDv7 = field(default_factory=UUIDv7)
    items_completed: int = 0
    items_total: int = 0
    has_checkpoint: bool = False
    force: bool = False


@dataclass(frozen=True, slots=True)
class TransitionResult:
    """Result of a state transition attempt."""

    success: bool
    new_status: RunStatus
    error: DomainError | None = None
    guard_failures: tuple[str, ...] = ()


GuardCondition = Callable[[TransitionContext], str | None]


def _require_all_items_completed(ctx: TransitionContext) -> str | None:
    """Guard: all items must be completed for successful completion."""
    if ctx.items_completed < ctx.items_total:
        return f"Not all items completed ({ctx.items_completed}/{ctx.items_total})"
    return None


def _require_items_completed_or_force(ctx: TransitionContext) -> str | None:
    """Guard: either all items completed or force cancellation."""
    if ctx.items_completed < ctx.items_total and not ctx.force:
        return f"Not all items completed ({ctx.items_completed}/{ctx.items_completed})"
    return None


def _require_checkpoint_for_resume(ctx: TransitionContext) -> str | None:
    """Guard: checkpoint must exist to resume from paused state."""
    if not ctx.has_checkpoint:
        return "No checkpoint available for resume"
    return None


def _noop_guard(_ctx: TransitionContext) -> str | None:
    """No-op guard that always passes."""
    return None


@dataclass(frozen=True, slots=True)
class Transition:
    """Definition of a single valid transition."""

    source: RunStatus
    target: RunStatus
    guards: tuple[GuardCondition, ...] = ()
    description: str = ""


_VALID_TRANSITIONS: list[Transition] = [
    Transition(source=RunStatus.CREATED, target=RunStatus.QUEUED, description="Queue"),
    Transition(source=RunStatus.QUEUED, target=RunStatus.STARTING, description="Begin"),
    Transition(
        source=RunStatus.QUEUED,
        target=RunStatus.CANCELLED,
        guards=(_require_items_completed_or_force,),
        description="Cancel before starting",
    ),
    Transition(source=RunStatus.STARTING, target=RunStatus.RUNNING, description="Active"),
    Transition(source=RunStatus.STARTING, target=RunStatus.FAILED, description="Init failed"),
    Transition(
        source=RunStatus.RUNNING,
        target=RunStatus.PAUSED,
        guards=(_noop_guard,),
        description="Pause",
    ),
    Transition(
        source=RunStatus.RUNNING,
        target=RunStatus.CANCELLING,
        description="Begin cancel",
    ),
    Transition(
        source=RunStatus.RUNNING,
        target=RunStatus.COMPLETED,
        guards=(_require_all_items_completed,),
        description="All items processed",
    ),
    Transition(source=RunStatus.RUNNING, target=RunStatus.FAILED, description="Failed"),
    Transition(source=RunStatus.RUNNING, target=RunStatus.TIMEDOUT, description="Timed out"),
    Transition(
        source=RunStatus.RUNNING,
        target=RunStatus.CANCELLED,
        guards=(_require_items_completed_or_force,),
        description="Force cancel while running",
    ),
    Transition(
        source=RunStatus.PAUSED,
        target=RunStatus.RUNNING,
        guards=(_require_checkpoint_for_resume,),
        description="Resume",
    ),
    Transition(source=RunStatus.PAUSED, target=RunStatus.CANCELLING, description="Cancel paused"),
    Transition(
        source=RunStatus.CANCELLING,
        target=RunStatus.COMPLETED,
        guards=(_require_items_completed_or_force,),
        description="Complete after cancel",
    ),
    Transition(
        source=RunStatus.CANCELLING,
        target=RunStatus.CANCELLED,
        guards=(_require_items_completed_or_force,),
        description="Final cancellation",
    ),
    Transition(
        source=RunStatus.CANCELLING,
        target=RunStatus.FAILED,
        description="Failed during cancel",
    ),
]


class RunStateMachine:
    """State machine for EvaluationRun lifecycle."""

    def __init__(self) -> None:
        """Initialize the state machine with the transition table."""
        self._transitions: dict[tuple[RunStatus, RunStatus], Transition] = {}
        for t in _VALID_TRANSITIONS:
            key = (t.source, t.target)
            self._transitions[key] = t

    def can_transition(
        self,
        current: RunStatus,
        target: RunStatus,
        ctx: TransitionContext | None = None,
    ) -> bool:
        """Check if a transition is valid without applying it."""
        result = self.transition(current, target, ctx or TransitionContext())
        return result.success

    def transition(
        self,
        current: RunStatus,
        target: RunStatus,
        ctx: TransitionContext,
    ) -> TransitionResult:
        """Attempt a state transition."""
        if current.is_terminal and target == current:
            return TransitionResult(success=True, new_status=target)

        if current.is_terminal:
            err = InvalidTransitionError(
                current_status=current,
                target_status=target,
            )
            return TransitionResult(success=False, new_status=current, error=err)

        key = (current, target)
        if key not in self._transitions:
            err = InvalidTransitionError(
                current_status=current,
                target_status=target,
            )
            return TransitionResult(success=False, new_status=current, error=err)

        transition = self._transitions[key]
        guard_failures: list[str] = []
        for guard in transition.guards:
            failure = guard(ctx)
            if failure is not None:
                guard_failures.append(failure)

        if guard_failures:
            return TransitionResult(
                success=False,
                new_status=current,
                error=InvalidTransitionError(
                    message=f"Guard conditions failed: {'; '.join(guard_failures)}",
                    current_status=current,
                    target_status=target,
                ),
                guard_failures=tuple(guard_failures),
            )

        return TransitionResult(success=True, new_status=target)

    def valid_targets(self, current: RunStatus) -> list[RunStatus]:
        """Return all valid target states from the given current state."""
        return [target for (source, target) in self._transitions if source == current]

    def is_terminal(self, status: RunStatus) -> bool:
        """Check if a status is terminal."""
        return status.is_terminal
