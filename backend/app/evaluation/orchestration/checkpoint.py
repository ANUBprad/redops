"""CheckpointManager — manages evaluation checkpoint creation.

Creates checkpoints at configured intervals to enable resume
from the last checkpoint after failure or cancellation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.evaluation.domain.factories.evaluation_factories import RunCheckpointFactory

if TYPE_CHECKING:
    from app.evaluation.domain.contracts.evaluation_contracts import (
        CheckpointRepository,
        ItemRepository,
    )
    from app.evaluation.domain.entities.evaluation_entities import EvaluationRun, RunCheckpoint


_DEFAULT_CHECKPOINT_INTERVAL: int = 50


class CheckpointManager:
    """Manages checkpoint creation at configured intervals.

    Determines whether a checkpoint should be created based on the
    number of completed items and the configured interval.
    """

    async def maybe_checkpoint(
        self,
        run: EvaluationRun,
        items_completed: int,
        item_repository: ItemRepository,
        checkpoint_repository: CheckpointRepository,
    ) -> RunCheckpoint | None:
        """Create checkpoint if the interval has been reached.

        Args:
            run: The current evaluation run.
            items_completed: Number of items completed so far.
            item_repository: Repository for reading completed items.
            checkpoint_repository: Repository for saving checkpoints.

        Returns:
            The created checkpoint, or None if interval not reached.

        """
        interval = run.config.limits.checkpoint_interval or _DEFAULT_CHECKPOINT_INTERVAL
        if items_completed == 0 or items_completed % interval != 0:
            return None

        existing = await checkpoint_repository.find_latest(run.id)
        next_number = (existing.checkpoint_number + 1) if existing else 1

        completed_items = await item_repository.find_by_run_id(run.id)
        completed_ids = tuple(
            item.id for item in completed_items if item.status.value == "completed"
        )

        checkpoint = RunCheckpointFactory.create(
            run_id=run.id,
            checkpoint_number=next_number,
            items_completed=items_completed,
            items_total=run.items_total,
            last_item_index=items_completed - 1,
            completed_item_ids=completed_ids,
        )

        await checkpoint_repository.save(checkpoint)
        run.save_checkpoint(checkpoint)

        return checkpoint

    def should_checkpoint(
        self,
        items_completed: int,
        checkpoint_interval: int,
    ) -> bool:
        """Determine if a checkpoint should be created now.

        Args:
            items_completed: Number of completed items.
            checkpoint_interval: Configured checkpoint interval.

        Returns:
            True if checkpoint should be created.

        """
        if items_completed == 0:
            return False
        return items_completed % checkpoint_interval == 0

    def next_checkpoint_target(
        self,
        items_completed: int,
        checkpoint_interval: int,
    ) -> int:
        """Calculate the next checkpoint target.

        Args:
            items_completed: Number of completed items.
            checkpoint_interval: Configured checkpoint interval.

        Returns:
            The item count at which the next checkpoint will occur.

        """
        current_batch = items_completed // checkpoint_interval
        return (current_batch + 1) * checkpoint_interval
