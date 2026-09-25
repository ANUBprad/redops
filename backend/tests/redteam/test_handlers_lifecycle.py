"""Handler-level lifecycle tests for AttackRun state transitions.

Verifies StartAttackRunHandler, CancelAttackRunHandler, FailAttackRunHandler,
and CompleteAttackRunHandler in isolation (no HTTP, no Temporal) — pure domain
state-machine coverage complementing the API and workflow suites.
"""

from __future__ import annotations

import pytest

from app.redteam.application.commands import (
    CancelAttackRunCommand,
    CompleteAttackRunCommand,
    FailAttackRunCommand,
    StartAttackRunCommand,
)
from app.redteam.application.handlers import (
    CancelAttackRunHandler,
    CompleteAttackRunHandler,
    FailAttackRunHandler,
    StartAttackRunHandler,
)
from app.redteam.domain.entities import AttackRun
from app.redteam.domain.enums import AttackStatus
from app.redteam.domain.value_objects import AttackConfiguration


class _InMemoryRunRepo:
    def __init__(self) -> None:
        self._runs: dict[str, AttackRun] = {}

    def seed(self, run: AttackRun) -> None:
        self._runs[str(run.id)] = run

    async def find_by_id(self, run_id: object) -> AttackRun | None:
        return self._runs.get(str(run_id))

    async def save(self, run: AttackRun) -> None:
        self._runs[str(run.id)] = run

    def get(self, run_id: str) -> AttackRun | None:
        return self._runs.get(run_id)


def _run(*, status: AttackStatus) -> AttackRun:
    run = AttackRun.create(
        configuration=AttackConfiguration(
            target_provider="test-provider",
            target_model="m",
        ),
    )
    if status == AttackStatus.QUEUED:
        run.queue()
    elif status == AttackStatus.RUNNING:
        run.queue()
        run.start(total_items=5)
    elif status == AttackStatus.COMPLETED:
        run.queue()
        run.start(total_items=5)
        run.complete()
    elif status == AttackStatus.FAILED:
        run.queue()
        run.start(total_items=5)
        run.fail("broken")
    elif status == AttackStatus.CANCELLED:
        run.queue()
        run.start(total_items=5)
        run.cancel()
    return run


@pytest.mark.asyncio
async def test_start_handler_creates_queued_then_running():
    repo = _InMemoryRunRepo()
    run = _run(status=AttackStatus.CREATED)
    repo.seed(run)

    handler = StartAttackRunHandler(repo)
    result = await handler.handle(StartAttackRunCommand(run_id=str(run.id), total_items=3))

    assert result.status == AttackStatus.RUNNING
    assert result.items_total == 3
    assert repo.get(str(run.id)).status == AttackStatus.RUNNING


@pytest.mark.asyncio
async def test_start_handler_skips_queue_for_queued_run():
    repo = _InMemoryRunRepo()
    run = _run(status=AttackStatus.QUEUED)
    repo.seed(run)

    handler = StartAttackRunHandler(repo)
    result = await handler.handle(StartAttackRunCommand(run_id=str(run.id), total_items=7))

    assert result.status == AttackStatus.RUNNING
    assert result.items_total == 7


@pytest.mark.asyncio
async def test_start_handler_conflict_terminal():
    repo = _InMemoryRunRepo()
    repo.seed(_run(status=AttackStatus.COMPLETED))

    from app.kernel.exceptions.errors import ConflictError

    handler = StartAttackRunHandler(repo)
    run_id = next(iter(repo._runs.keys()))
    with pytest.raises(ConflictError):
        await handler.handle(StartAttackRunCommand(run_id=run_id, total_items=1))


@pytest.mark.asyncio
async def test_cancel_handler_idempotent_for_already_cancelled():
    repo = _InMemoryRunRepo()
    run = _run(status=AttackStatus.CANCELLED)
    repo.seed(run)
    run_id = str(run.id)

    handler = CancelAttackRunHandler(repo)
    result = await handler.handle(CancelAttackRunCommand(run_id=run_id))

    assert result.status == AttackStatus.CANCELLED
    # The handler skips the save for already-cancelled runs.
    assert repo.get(run_id).status == AttackStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_handler_transitions_running_to_cancelled():
    repo = _InMemoryRunRepo()
    run = _run(status=AttackStatus.RUNNING)
    repo.seed(run)
    run_id = str(run.id)

    handler = CancelAttackRunHandler(repo)
    result = await handler.handle(CancelAttackRunCommand(run_id=run_id))

    assert result.status == AttackStatus.CANCELLED
    assert repo.get(run_id).status == AttackStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_handler_conflict_terminal():
    from app.kernel.exceptions.errors import ConflictError

    repo = _InMemoryRunRepo()
    repo.seed(_run(status=AttackStatus.COMPLETED))
    run_id = next(iter(repo._runs.keys()))

    handler = CancelAttackRunHandler(repo)
    with pytest.raises(ConflictError):
        await handler.handle(CancelAttackRunCommand(run_id=run_id))


@pytest.mark.asyncio
async def test_fail_handler_marks_running_run_failed():
    repo = _InMemoryRunRepo()
    run = _run(status=AttackStatus.RUNNING)
    repo.seed(run)
    run_id = str(run.id)

    handler = FailAttackRunHandler(repo)
    result = await handler.handle(FailAttackRunCommand(run_id=run_id, error_message="bad"))

    assert result.status == AttackStatus.FAILED
    assert repo.get(run_id).status == AttackStatus.FAILED


@pytest.mark.asyncio
async def test_fail_handler_conflict_terminal():
    from app.kernel.exceptions.errors import ConflictError

    repo = _InMemoryRunRepo()
    repo.seed(_run(status=AttackStatus.COMPLETED))
    run_id = next(iter(repo._runs.keys()))

    handler = FailAttackRunHandler(repo)
    with pytest.raises(ConflictError):
        await handler.handle(FailAttackRunCommand(run_id=run_id, error_message="x"))


@pytest.mark.asyncio
async def test_complete_handler_transitions_running_to_completed():
    repo = _InMemoryRunRepo()
    run = _run(status=AttackStatus.RUNNING)
    repo.seed(run)
    run_id = str(run.id)

    handler = CompleteAttackRunHandler(repo)
    result = await handler.handle(CompleteAttackRunCommand(run_id=run_id))

    assert result.status == AttackStatus.COMPLETED
    assert repo.get(run_id).status == AttackStatus.COMPLETED


@pytest.mark.asyncio
async def test_complete_handler_conflict_terminal():
    from app.kernel.exceptions.errors import ConflictError

    repo = _InMemoryRunRepo()
    repo.seed(_run(status=AttackStatus.CANCELLED))
    run_id = next(iter(repo._runs.keys()))

    handler = CompleteAttackRunHandler(repo)
    with pytest.raises(ConflictError):
        await handler.handle(CompleteAttackRunCommand(run_id=run_id))
