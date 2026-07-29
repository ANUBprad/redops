"""Tests for evaluation run application handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.evaluation.application.run_commands import (
    CancelEvaluationRunCommand,
    CompleteEvaluationRunCommand,
    CreateEvaluationRunCommand,
    FailEvaluationRunCommand,
    GetEvaluationRunQuery,
    ListEvaluationRunsQuery,
    RetryEvaluationRunCommand,
    UpdateRunProgressCommand,
)
from app.evaluation.application.run_handlers import (
    CancelEvaluationRunHandler,
    CompleteEvaluationRunHandler,
    CreateEvaluationRunHandler,
    FailEvaluationRunHandler,
    GetEvaluationRunHandler,
    ListEvaluationRunsHandler,
    RetryEvaluationRunHandler,
    UpdateRunProgressHandler,
)
from app.evaluation.domain.contracts.evaluation_contracts import (
    PaginatedRuns,
    RunRepository,
)
from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
from app.evaluation.domain.enums.evaluation_enums import RunStatus
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError, NotFoundError, ValidationError


def _make_run(
    *,
    name: str = "test-run",
    status: RunStatus = RunStatus.CREATED,
) -> EvaluationRun:
    """Create a minimal EvaluationRun for testing."""
    from app.evaluation.domain.enums.evaluation_enums import EvaluationType
    from app.evaluation.domain.value_objects.evaluation_value_objects import (
        EvaluationConfiguration,
        EvaluationProfile,
    )

    config = EvaluationConfiguration(
        name=name,
        eval_type=EvaluationType.SINGLE,
        profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
        metrics=("accuracy",),
    )
    run = EvaluationRun(
        evaluation_name=name,
        config=config,
        profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
    )
    if status == RunStatus.QUEUED:
        run.queue()
    elif status == RunStatus.RUNNING:
        run.queue()
        run.start(total_items=10)
    elif status == RunStatus.COMPLETED:
        run.queue()
        run.start(total_items=1)
        run.record_item_success()
        run.complete()
    elif status == RunStatus.FAILED:
        run.queue()
        run.start(total_items=1)
        run.fail(error_code="ERR", error_message="boom")
    run.collect_events()
    return run


def _mock_repo(**methods: object) -> RunRepository:
    """Create a mock repository with configurable methods."""
    repo = AsyncMock(spec=RunRepository)
    for name, value in methods.items():
        setattr(repo, name, value)
    return repo


class TestCreateEvaluationRunHandler:
    """Tests for CreateEvaluationRunHandler."""

    async def test_create_run(self) -> None:
        """Handler creates and persists a run."""
        repo = _mock_repo(save=AsyncMock())
        handler = CreateEvaluationRunHandler(repo)
        command = CreateEvaluationRunCommand(
            evaluation_name="new-run",
            provider="openai",
            model="gpt-4",
            metrics=("accuracy",),
        )

        result = await handler.handle(command)

        assert result.evaluation_name == "new-run"
        assert result.profile.provider_name == "openai"
        repo.save.assert_called_once()

    async def test_create_run_with_evaluation_id(self) -> None:
        """Handler creates run linked to evaluation definition."""
        repo = _mock_repo(save=AsyncMock())
        handler = CreateEvaluationRunHandler(repo)
        command = CreateEvaluationRunCommand(
            evaluation_name="linked-run",
            evaluation_id="eval-123",
            provider="openai",
            model="gpt-4",
        )

        result = await handler.handle(command)

        assert result.evaluation_id == "eval-123"

    async def test_create_run_missing_provider_raises(self) -> None:
        """Handler raises ValidationError when provider missing."""
        repo = _mock_repo()
        handler = CreateEvaluationRunHandler(repo)
        command = CreateEvaluationRunCommand(
            evaluation_name="test",
            provider="",
            model="gpt-4",
        )

        with pytest.raises(ValidationError, match="Provider"):
            await handler.handle(command)

    async def test_create_run_missing_model_raises(self) -> None:
        """Handler raises ValidationError when model missing."""
        repo = _mock_repo()
        handler = CreateEvaluationRunHandler(repo)
        command = CreateEvaluationRunCommand(
            evaluation_name="test",
            provider="openai",
            model="",
        )

        with pytest.raises(ValidationError, match="Model"):
            await handler.handle(command)


class TestGetEvaluationRunHandler:
    """Tests for GetEvaluationRunHandler."""

    async def test_get_run(self) -> None:
        """Handler returns run by ID."""
        run = _make_run()
        repo = _mock_repo(find_by_id=AsyncMock(return_value=run))
        handler = GetEvaluationRunHandler(repo)
        query = GetEvaluationRunQuery(run_id=str(run.id))

        result = await handler.handle(query)

        assert result.id == run.id

    async def test_get_run_not_found_raises(self) -> None:
        """Handler raises NotFoundError when not found."""
        repo = _mock_repo(find_by_id=AsyncMock(return_value=None))
        handler = GetEvaluationRunHandler(repo)
        query = GetEvaluationRunQuery(run_id=str(UUIDv7()))

        with pytest.raises(NotFoundError, match="not found"):
            await handler.handle(query)


class TestListEvaluationRunsHandler:
    """Tests for ListEvaluationRunsHandler."""

    async def test_list_runs(self) -> None:
        """Handler returns paginated results."""
        run = _make_run()
        paginated = PaginatedRuns(items=[run], total=1, page=1, page_size=20)
        repo = _mock_repo(list=AsyncMock(return_value=paginated))
        handler = ListEvaluationRunsHandler(repo)
        query = ListEvaluationRunsQuery()

        result = await handler.handle(query)

        assert result.total == 1
        assert len(result.items) == 1


class TestCancelEvaluationRunHandler:
    """Tests for CancelEvaluationRunHandler."""

    async def test_cancel_run(self) -> None:
        """Handler cancels a running run."""
        run = _make_run(status=RunStatus.RUNNING)
        repo = _mock_repo(
            find_by_id=AsyncMock(return_value=run),
            save=AsyncMock(),
        )
        handler = CancelEvaluationRunHandler(repo)
        command = CancelEvaluationRunCommand(run_id=str(run.id))

        result = await handler.handle(command)

        assert result.status in (RunStatus.CANCELLING, RunStatus.CANCELLED)
        repo.save.assert_called_once()

    async def test_cancel_not_found_raises(self) -> None:
        """Handler raises NotFoundError when run not found."""
        repo = _mock_repo(find_by_id=AsyncMock(return_value=None))
        handler = CancelEvaluationRunHandler(repo)
        command = CancelEvaluationRunCommand(run_id=str(UUIDv7()))

        with pytest.raises(NotFoundError, match="not found"):
            await handler.handle(command)


class TestFailEvaluationRunHandler:
    """Tests for FailEvaluationRunHandler."""

    async def test_fail_run(self) -> None:
        """Handler fails a running run."""
        run = _make_run(status=RunStatus.RUNNING)
        repo = _mock_repo(
            find_by_id=AsyncMock(return_value=run),
            save=AsyncMock(),
        )
        handler = FailEvaluationRunHandler(repo)
        command = FailEvaluationRunCommand(
            run_id=str(run.id),
            error_code="PROVIDER_ERROR",
            error_message="API timeout",
        )

        result = await handler.handle(command)

        assert result.status == RunStatus.FAILED
        repo.save.assert_called_once()


class TestCompleteEvaluationRunHandler:
    """Tests for CompleteEvaluationRunHandler."""

    async def test_complete_run(self) -> None:
        """Handler completes a running run with all items done."""
        run = _make_run(status=RunStatus.RUNNING)
        run.items_total = 1
        run.items_completed = 1
        repo = _mock_repo(
            find_by_id=AsyncMock(return_value=run),
            save=AsyncMock(),
        )
        handler = CompleteEvaluationRunHandler(repo)
        command = CompleteEvaluationRunCommand(run_id=str(run.id))

        result = await handler.handle(command)

        assert result.status == RunStatus.COMPLETED
        repo.save.assert_called_once()


class TestRetryEvaluationRunHandler:
    """Tests for RetryEvaluationRunHandler."""

    async def test_retry_failed_run(self) -> None:
        """Handler retries a failed run by creating a new one."""
        run = _make_run(status=RunStatus.FAILED)
        repo = _mock_repo(
            find_by_id=AsyncMock(return_value=run),
            save=AsyncMock(),
        )
        handler = RetryEvaluationRunHandler(repo)
        command = RetryEvaluationRunCommand(run_id=str(run.id))

        result = await handler.handle(command)

        assert result.status == RunStatus.CREATED
        assert result.id != run.id
        repo.save.assert_called_once()

    async def test_retry_non_failed_run_raises(self) -> None:
        """Handler raises ConflictError when run is not failed."""
        run = _make_run(status=RunStatus.RUNNING)
        repo = _mock_repo(
            find_by_id=AsyncMock(return_value=run),
            save=AsyncMock(),
        )
        handler = RetryEvaluationRunHandler(repo)
        command = RetryEvaluationRunCommand(run_id=str(run.id))

        with pytest.raises(ConflictError, match="Only failed"):
            await handler.handle(command)


class TestUpdateRunProgressHandler:
    """Tests for UpdateRunProgressHandler."""

    async def test_update_progress(self) -> None:
        """Handler updates run progress."""
        run = _make_run(status=RunStatus.RUNNING)
        repo = _mock_repo(
            find_by_id=AsyncMock(return_value=run),
            persist_progress=AsyncMock(),
        )
        handler = UpdateRunProgressHandler(repo)
        command = UpdateRunProgressCommand(
            run_id=str(run.id),
            token_input=100,
            token_output=50,
            cost_usd=0.01,
            latency_ms=200,
        )

        result = await handler.handle(command)

        assert result.token_input == 100
        assert result.token_output == 50
        assert result.cost == 0.01
        repo.persist_progress.assert_called_once()
