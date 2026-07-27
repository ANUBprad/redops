"""Tests for CheckpointManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.evaluation.orchestration.checkpoint import CheckpointManager
from app.evaluation.domain.enums.evaluation_enums import EvaluationType
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    EvaluationConfiguration,
    EvaluationProfile,
    ExecutionLimits,
)
from app.kernel.entities.base import UUIDv7


def _make_run(checkpoint_interval: int = 5, total_items: int = 20):
    """Create an EvaluationRun with the given checkpoint interval."""
    from app.evaluation.domain.entities.evaluation_entities import EvaluationRun

    config = EvaluationConfiguration(
        name="test",
        eval_type=EvaluationType.DATASET,
        profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
        metrics=("accuracy",),
        dataset=MagicMock(row_count=total_items),
        limits=ExecutionLimits(checkpoint_interval=checkpoint_interval),
    )
    run = EvaluationRun(
        evaluation_name="test",
        config=config,
        profile=config.profile,
    )
    run.queue()
    run.start(total_items=total_items)
    return run


# ---------------------------------------------------------------------------
# should_checkpoint
# ---------------------------------------------------------------------------


class TestCheckpointManagerShouldCheckpoint:
    """Tests for CheckpointManager.should_checkpoint()."""

    def test_zero_items_returns_false(self) -> None:
        """0 completed items should not trigger checkpoint."""
        mgr = CheckpointManager()
        assert mgr.should_checkpoint(0, 5) is False

    def test_interval_reached_returns_true(self) -> None:
        """Completed items equal to interval should trigger checkpoint."""
        mgr = CheckpointManager()
        assert mgr.should_checkpoint(5, 5) is True

    def test_interval_not_reached_returns_false(self) -> None:
        """Completed items not reaching interval should not trigger checkpoint."""
        mgr = CheckpointManager()
        assert mgr.should_checkpoint(3, 5) is False

    def test_multiple_intervals(self) -> None:
        """Completed items at multiples of interval should trigger checkpoint."""
        mgr = CheckpointManager()
        assert mgr.should_checkpoint(10, 5) is True
        assert mgr.should_checkpoint(15, 5) is True
        assert mgr.should_checkpoint(20, 5) is True

    def test_one_item_interval(self) -> None:
        """Interval of 1 should trigger at every item."""
        mgr = CheckpointManager()
        assert mgr.should_checkpoint(1, 1) is True
        assert mgr.should_checkpoint(7, 1) is True


# ---------------------------------------------------------------------------
# next_checkpoint_target
# ---------------------------------------------------------------------------


class TestCheckpointManagerNextCheckpointTarget:
    """Tests for CheckpointManager.next_checkpoint_target()."""

    def test_zero_completed(self) -> None:
        """0 completed should target the first interval."""
        mgr = CheckpointManager()
        assert mgr.next_checkpoint_target(0, 5) == 5

    def test_partial_batch(self) -> None:
        """Partial batch should target next interval multiple."""
        mgr = CheckpointManager()
        assert mgr.next_checkpoint_target(3, 5) == 5
        assert mgr.next_checkpoint_target(7, 5) == 10

    def test_exact_boundary(self) -> None:
        """Exact boundary should target next interval multiple."""
        mgr = CheckpointManager()
        assert mgr.next_checkpoint_target(5, 5) == 10
        assert mgr.next_checkpoint_target(10, 5) == 15

    def test_single_interval(self) -> None:
        """Interval of 1 should always increment by 1."""
        mgr = CheckpointManager()
        assert mgr.next_checkpoint_target(0, 1) == 1
        assert mgr.next_checkpoint_target(5, 1) == 6


# ---------------------------------------------------------------------------
# maybe_checkpoint
# ---------------------------------------------------------------------------


class TestCheckpointManagerMaybeCheckpoint:
    """Tests for CheckpointManager.maybe_checkpoint()."""

    async def test_returns_none_when_interval_not_reached(self) -> None:
        """Should return None when interval is not reached."""
        run = _make_run(checkpoint_interval=5)
        item_repo = MagicMock()
        checkpoint_repo = MagicMock()
        mgr = CheckpointManager()

        result = await mgr.maybe_checkpoint(run, 3, item_repo, checkpoint_repo)
        assert result is None

    async def test_returns_none_at_zero(self) -> None:
        """Should return None when 0 items completed."""
        run = _make_run(checkpoint_interval=5)
        item_repo = MagicMock()
        checkpoint_repo = MagicMock()
        mgr = CheckpointManager()

        result = await mgr.maybe_checkpoint(run, 0, item_repo, checkpoint_repo)
        assert result is None

    async def test_creates_first_checkpoint(self) -> None:
        """Should create checkpoint number 1 when no existing checkpoint."""
        run = _make_run(checkpoint_interval=5, total_items=20)
        run.items_completed = 5
        item_repo = MagicMock()
        item_repo.find_by_run_id = AsyncMock(return_value=[])
        checkpoint_repo = MagicMock()
        checkpoint_repo.find_latest = AsyncMock(return_value=None)
        checkpoint_repo.save = AsyncMock()

        mgr = CheckpointManager()
        result = await mgr.maybe_checkpoint(run, 5, item_repo, checkpoint_repo)

        assert result is not None
        assert result.checkpoint_number == 1
        assert result.items_completed == 5
        checkpoint_repo.save.assert_called_once()

    async def test_creates_incremental_checkpoint(self) -> None:
        """Should increment checkpoint number when existing checkpoint exists."""
        run = _make_run(checkpoint_interval=5, total_items=20)
        run.items_completed = 10

        existing_checkpoint = MagicMock()
        existing_checkpoint.checkpoint_number = 2

        item_repo = MagicMock()
        item_repo.find_by_run_id = AsyncMock(return_value=[])
        checkpoint_repo = MagicMock()
        checkpoint_repo.find_latest = AsyncMock(return_value=existing_checkpoint)
        checkpoint_repo.save = AsyncMock()

        mgr = CheckpointManager()
        result = await mgr.maybe_checkpoint(run, 10, item_repo, checkpoint_repo)

        assert result is not None
        assert result.checkpoint_number == 3

    async def test_saves_checkpoint_to_run(self) -> None:
        """Created checkpoint should be saved on the run."""
        run = _make_run(checkpoint_interval=5, total_items=20)
        run.items_completed = 5
        item_repo = MagicMock()
        item_repo.find_by_run_id = AsyncMock(return_value=[])
        checkpoint_repo = MagicMock()
        checkpoint_repo.find_latest = AsyncMock(return_value=None)
        checkpoint_repo.save = AsyncMock()

        mgr = CheckpointManager()
        await mgr.maybe_checkpoint(run, 5, item_repo, checkpoint_repo)

        assert run.checkpoint is not None
        assert run.checkpoint.checkpoint_number == 1
