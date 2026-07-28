"""Tests for in-memory repository implementations."""

from __future__ import annotations

from app.evaluation.domain.entities.evaluation_entities import (
    EvaluationItem,
    EvaluationRun,
    RunCheckpoint,
)
from app.evaluation.domain.enums.evaluation_enums import EvaluationType, ItemStatus, RunStatus
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    EvaluationConfiguration,
    EvaluationProfile,
)
from app.evaluation.orchestration.repositories import (
    InMemoryCheckpointRepository,
    InMemoryEventPublisher,
    InMemoryItemRepository,
    InMemoryRunRepository,
)
from app.kernel.entities.base import UUIDv7


def _make_run(name: str = "test", status: RunStatus = RunStatus.CREATED) -> EvaluationRun:
    """Create a minimal EvaluationRun."""
    config = EvaluationConfiguration(
        name=name,
        eval_type=EvaluationType.SINGLE,
        profile=EvaluationProfile(provider_name="o", model_id="m"),
        metrics=("accuracy",),
    )
    run = EvaluationRun(evaluation_name=name, config=config, profile=config.profile)
    if status == RunStatus.QUEUED:
        run.queue()
    elif status == RunStatus.RUNNING:
        run.queue()
        run.start(total_items=5)
    elif status == RunStatus.COMPLETED:
        run.queue()
        run.start(total_items=5)
        run.items_completed = 5
        run.complete()
    return run


def _make_item(
    run_id: UUIDv7, index: int, status: ItemStatus = ItemStatus.PENDING
) -> EvaluationItem:
    """Create a minimal EvaluationItem."""
    item = EvaluationItem(run_id=run_id, index=index)
    if status == ItemStatus.RUNNING:
        item.start()
    elif status == ItemStatus.COMPLETED:
        item.start()
        from app.evaluation.domain.entities.evaluation_entities import ItemResult

        item.complete(ItemResult(item_id=item.id, item_index=index, status=ItemStatus.COMPLETED))
    elif status == ItemStatus.FAILED:
        item.start()
        item.fail("test error")
    return item


# ---------------------------------------------------------------------------
# InMemoryRunRepository
# ---------------------------------------------------------------------------


class TestInMemoryRunRepository:
    """Tests for InMemoryRunRepository."""

    async def test_save_and_find_by_id(self) -> None:
        """Saved run should be retrievable by ID."""
        repo = InMemoryRunRepository()
        run = _make_run()
        await repo.save(run)
        found = await repo.find_by_id(run.id)
        assert found is not None
        assert found.id == run.id

    async def test_find_by_id_nonexistent(self) -> None:
        """Nonexistent ID should return None."""
        repo = InMemoryRunRepository()
        found = await repo.find_by_id(UUIDv7.generate())
        assert found is None

    async def test_find_by_status(self) -> None:
        """Should return runs matching the given status."""
        repo = InMemoryRunRepository()
        r1 = _make_run("r1", RunStatus.QUEUED)
        r2 = _make_run("r2", RunStatus.QUEUED)
        r3 = _make_run("r3", RunStatus.COMPLETED)
        await repo.save(r1)
        await repo.save(r2)
        await repo.save(r3)

        queued = await repo.find_by_status(RunStatus.QUEUED)
        assert len(queued) == 2

        completed = await repo.find_by_status(RunStatus.COMPLETED)
        assert len(completed) == 1

    async def test_find_by_status_pagination(self) -> None:
        """Should respect limit and offset."""
        repo = InMemoryRunRepository()
        for i in range(10):
            await repo.save(_make_run(f"r{i}", RunStatus.QUEUED))

        page = await repo.find_by_status(RunStatus.QUEUED, limit=3, offset=2)
        assert len(page) == 3

    async def test_delete_existing(self) -> None:
        """Deleting an existing run should return True and remove it."""
        repo = InMemoryRunRepository()
        run = _make_run()
        await repo.save(run)
        result = await repo.delete(run.id)
        assert result is True
        assert await repo.find_by_id(run.id) is None

    async def test_delete_nonexistent(self) -> None:
        """Deleting a nonexistent run should return False."""
        repo = InMemoryRunRepository()
        result = await repo.delete(UUIDv7.generate())
        assert result is False

    async def test_overwrite_save(self) -> None:
        """Saving same ID twice should overwrite."""
        repo = InMemoryRunRepository()
        run = _make_run()
        await repo.save(run)
        found1 = await repo.find_by_id(run.id)
        assert found1 is run

        run2 = _make_run()
        run2.id = run.id
        await repo.save(run2)
        found2 = await repo.find_by_id(run.id)
        assert found2 is run2


# ---------------------------------------------------------------------------
# InMemoryItemRepository
# ---------------------------------------------------------------------------


class TestInMemoryItemRepository:
    """Tests for InMemoryItemRepository."""

    async def test_save_many_and_find_by_run_id(self) -> None:
        """Saved items should be retrievable by run_id."""
        repo = InMemoryItemRepository()
        run_id = UUIDv7.generate()
        items = [_make_item(run_id, i) for i in range(3)]
        await repo.save_many(items)

        found = await repo.find_by_run_id(run_id)
        assert len(found) == 3

    async def test_find_by_run_id_pagination(self) -> None:
        """Should respect limit and offset."""
        repo = InMemoryItemRepository()
        run_id = UUIDv7.generate()
        items = [_make_item(run_id, i) for i in range(10)]
        await repo.save_many(items)

        page = await repo.find_by_run_id(run_id, limit=3, offset=5)
        assert len(page) == 3

    async def test_find_by_run_id_empty(self) -> None:
        """No items for a run should return empty list."""
        repo = InMemoryItemRepository()
        found = await repo.find_by_run_id(UUIDv7.generate())
        assert found == []

    async def test_find_pending_by_run_id(self) -> None:
        """Should only return PENDING items."""
        repo = InMemoryItemRepository()
        run_id = UUIDv7.generate()
        pending = _make_item(run_id, 0, ItemStatus.PENDING)
        completed = _make_item(run_id, 1, ItemStatus.COMPLETED)
        await repo.save_many([pending, completed])

        found = await repo.find_pending_by_run_id(run_id)
        assert len(found) == 1
        assert found[0].status == ItemStatus.PENDING

    async def test_items_across_runs_are_separated(self) -> None:
        """Items from different runs should not mix."""
        repo = InMemoryItemRepository()
        run1 = UUIDv7.generate()
        run2 = UUIDv7.generate()
        await repo.save_many([_make_item(run1, 0), _make_item(run1, 1)])
        await repo.save_many([_make_item(run2, 0)])

        found1 = await repo.find_by_run_id(run1)
        found2 = await repo.find_by_run_id(run2)
        assert len(found1) == 2
        assert len(found2) == 1


# ---------------------------------------------------------------------------
# InMemoryCheckpointRepository
# ---------------------------------------------------------------------------


class TestInMemoryCheckpointRepository:
    """Tests for InMemoryCheckpointRepository."""

    def _make_checkpoint(self, run_id: UUIDv7, number: int) -> RunCheckpoint:
        """Create a minimal RunCheckpoint."""
        return RunCheckpoint(
            run_id=run_id,
            checkpoint_number=number,
            items_completed=number * 10,
            items_total=100,
            last_item_index=(number * 10) - 1,
        )

    async def test_save_and_find_latest(self) -> None:
        """Saved checkpoints should return the latest by number."""
        repo = InMemoryCheckpointRepository()
        run_id = UUIDv7.generate()
        cp1 = self._make_checkpoint(run_id, 1)
        cp2 = self._make_checkpoint(run_id, 2)
        await repo.save(cp1)
        await repo.save(cp2)

        latest = await repo.find_latest(run_id)
        assert latest is not None
        assert latest.checkpoint_number == 2

    async def test_find_latest_none(self) -> None:
        """No checkpoints should return None."""
        repo = InMemoryCheckpointRepository()
        latest = await repo.find_latest(UUIDv7.generate())
        assert latest is None

    async def test_find_by_number(self) -> None:
        """Should find a specific checkpoint by number."""
        repo = InMemoryCheckpointRepository()
        run_id = UUIDv7.generate()
        cp1 = self._make_checkpoint(run_id, 1)
        cp2 = self._make_checkpoint(run_id, 2)
        await repo.save(cp1)
        await repo.save(cp2)

        found = await repo.find_by_number(run_id, 1)
        assert found is not None
        assert found.checkpoint_number == 1

    async def test_find_by_number_not_found(self) -> None:
        """Nonexistent checkpoint number should return None."""
        repo = InMemoryCheckpointRepository()
        run_id = UUIDv7.generate()
        await repo.save(self._make_checkpoint(run_id, 1))
        found = await repo.find_by_number(run_id, 99)
        assert found is None

    async def test_prune_keeps_latest(self) -> None:
        """Prune should keep the most recent checkpoints."""
        repo = InMemoryCheckpointRepository()
        run_id = UUIDv7.generate()
        for i in range(1, 8):
            await repo.save(self._make_checkpoint(run_id, i))

        removed = await repo.prune(run_id, keep_latest=3)
        assert removed == 4

        latest = await repo.find_latest(run_id)
        assert latest is not None
        assert latest.checkpoint_number == 7

    async def test_prune_nothing_to_prune(self) -> None:
        """Prune with fewer checkpoints than keep_latest should remove 0."""
        repo = InMemoryCheckpointRepository()
        run_id = UUIDv7.generate()
        await repo.save(self._make_checkpoint(run_id, 1))
        await repo.save(self._make_checkpoint(run_id, 2))

        removed = await repo.prune(run_id, keep_latest=5)
        assert removed == 0

    async def test_prune_empty(self) -> None:
        """Prune with no checkpoints should remove 0."""
        repo = InMemoryCheckpointRepository()
        removed = await repo.prune(UUIDv7.generate(), keep_latest=3)
        assert removed == 0

    async def test_checkpoints_per_run_isolation(self) -> None:
        """Checkpoints from different runs should not mix."""
        repo = InMemoryCheckpointRepository()
        run1 = UUIDv7.generate()
        run2 = UUIDv7.generate()
        await repo.save(self._make_checkpoint(run1, 1))
        await repo.save(self._make_checkpoint(run2, 1))

        latest1 = await repo.find_latest(run1)
        latest2 = await repo.find_latest(run2)
        assert latest1 is not None
        assert latest2 is not None
        assert latest1.run_id == run1
        assert latest2.run_id == run2


# ---------------------------------------------------------------------------
# InMemoryEventPublisher
# ---------------------------------------------------------------------------


class TestInMemoryEventPublisher:
    """Tests for InMemoryEventPublisher."""

    async def test_publish_and_get_events(self) -> None:
        """Published events should be retrievable."""
        publisher = InMemoryEventPublisher()
        event = {"type": "test", "data": "hello"}
        await publisher.publish(event)
        events = publisher.get_events()
        assert len(events) == 1
        assert events[0] == event

    async def test_publish_many(self) -> None:
        """publish_many should add all events."""
        publisher = InMemoryEventPublisher()
        events = [{"type": "a"}, {"type": "b"}, {"type": "c"}]
        await publisher.publish_many(events)
        assert len(publisher.get_events()) == 3

    async def test_get_events_returns_copy(self) -> None:
        """get_events should return a copy, not the internal list."""
        publisher = InMemoryEventPublisher()
        await publisher.publish({"type": "a"})
        events = publisher.get_events()
        events.clear()
        assert len(publisher.get_events()) == 1

    async def test_clear_events(self) -> None:
        """clear_events should remove all stored events."""
        publisher = InMemoryEventPublisher()
        await publisher.publish({"type": "a"})
        await publisher.publish({"type": "b"})
        publisher.clear_events()
        assert publisher.get_events() == []

    async def test_empty_publisher(self) -> None:
        """New publisher should have no events."""
        publisher = InMemoryEventPublisher()
        assert publisher.get_events() == []
