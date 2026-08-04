"""Shared checkpoint interval logic.

Extracts the common checkpoint scheduling logic used by both
evaluation and agent checkpoint managers.
"""

from __future__ import annotations


def should_checkpoint(completed: int, interval: int) -> bool:
    """Determine if a checkpoint should be created now.

    Args:
        completed: Number of completed items or steps.
        interval: Configured checkpoint interval.

    Returns:
        True if checkpoint should be created.

    """
    if completed == 0:
        return False
    return completed % interval == 0


def next_checkpoint_target(completed: int, interval: int) -> int:
    """Calculate the next checkpoint target.

    Args:
        completed: Number of completed items or steps.
        interval: Configured checkpoint interval.

    Returns:
        The count at which the next checkpoint will occur.

    """
    current_batch = completed // interval
    return (current_batch + 1) * interval
