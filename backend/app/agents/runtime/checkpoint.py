"""AgentCheckpointManager — manages agent checkpoint creation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.domain.contracts.agent_contracts import AgentCheckpointRepository
    from app.agents.domain.entities.agent_entities import AgentRun


_DEFAULT_CHECKPOINT_INTERVAL: int = 5


class AgentCheckpointManager:
    """Manages checkpoint creation at configured intervals."""

    async def maybe_checkpoint(
        self,
        run: AgentRun,
        steps_completed: int,
        checkpoint_repository: AgentCheckpointRepository,
    ) -> None:
        """Create checkpoint if the interval has been reached."""
        interval = run.config.checkpoint_interval or _DEFAULT_CHECKPOINT_INTERVAL
        if steps_completed == 0 or steps_completed % interval != 0:
            return

        from app.agents.domain.value_objects.agent_value_objects import AgentCheckpoint

        existing = await checkpoint_repository.find_latest(run.id)
        next_number = (existing.checkpoint_number + 1) if existing else 1

        checkpoint = AgentCheckpoint(
            run_id=str(run.id),
            checkpoint_number=next_number,
            steps_completed=steps_completed,
            steps_total=run.steps_total,
            last_step_index=steps_completed - 1,
        )

        await checkpoint_repository.save(checkpoint)
        run.save_checkpoint(checkpoint)

    def should_checkpoint(
        self,
        steps_completed: int,
        checkpoint_interval: int,
    ) -> bool:
        """Determine if a checkpoint should be created now."""
        if steps_completed == 0:
            return False
        return steps_completed % checkpoint_interval == 0

    def next_checkpoint_target(
        self,
        steps_completed: int,
        checkpoint_interval: int,
    ) -> int:
        """Calculate the next checkpoint target."""
        current_batch = steps_completed // checkpoint_interval
        return (current_batch + 1) * checkpoint_interval
