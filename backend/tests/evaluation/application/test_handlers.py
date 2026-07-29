"""Tests for evaluation application handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.evaluation.application.commands import (
    ArchiveEvaluationCommand,
    CreateEvaluationCommand,
    DeleteEvaluationCommand,
    DuplicateEvaluationCommand,
    GetEvaluationQuery,
    ListEvaluationsQuery,
    MarkReadyEvaluationCommand,
    UpdateEvaluationCommand,
)
from app.evaluation.application.handlers import (
    ArchiveEvaluationHandler,
    CreateEvaluationHandler,
    DeleteEvaluationHandler,
    DuplicateEvaluationHandler,
    GetEvaluationHandler,
    ListEvaluationsHandler,
    MarkReadyEvaluationHandler,
    UpdateEvaluationHandler,
)
from app.evaluation.domain.contracts.evaluation_contracts import (
    EvaluationRepository,
    PaginatedEvaluations,
)
from app.evaluation.domain.entities.evaluation_definition import Evaluation
from app.evaluation.domain.enums.evaluation_enums import EvaluationStatus
from app.evaluation.domain.value_objects.evaluation_definition_vos import (
    EvaluationName,
    MetricId,
    ProviderId,
)
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError, NotFoundError


def _make_evaluation(
    *,
    name: str = "test-eval",
    project_id: str = "proj-1",
    status: EvaluationStatus = EvaluationStatus.DRAFT,
) -> Evaluation:
    """Create a minimal Evaluation for testing."""
    ev = Evaluation.create(
        project_id=project_id,
        dataset_id="ds-1",
        name=EvaluationName(value=name),
        provider=ProviderId(value="openai"),
        model="gpt-4",
        metrics=(MetricId(value="accuracy"),),
    )
    if status == EvaluationStatus.READY:
        ev.mark_ready()
    elif status == EvaluationStatus.ARCHIVED:
        ev.archive()
    ev.collect_events()  # clear creation events
    return ev


def _mock_repo(**methods: object) -> EvaluationRepository:
    """Create a mock repository with configurable methods."""
    repo = AsyncMock(spec=EvaluationRepository)
    for name, value in methods.items():
        setattr(repo, name, value)
    return repo


class TestCreateEvaluationHandler:
    """Tests for CreateEvaluationHandler."""

    async def test_create_evaluation(self) -> None:
        """Handler creates and persists an evaluation."""
        repo = _mock_repo(
            exists_by_name_in_project=AsyncMock(return_value=False),
            create=AsyncMock(),
        )
        handler = CreateEvaluationHandler(repo)
        command = CreateEvaluationCommand(
            project_id="proj-1",
            dataset_id="ds-1",
            name="new-eval",
            provider="openai",
            model="gpt-4",
            metrics=("accuracy",),
        )

        result = await handler.handle(command)

        assert str(result.name.value) == "new-eval"
        assert result.project_id == "proj-1"
        repo.create.assert_called_once()

    async def test_create_duplicate_name_raises(self) -> None:
        """Handler raises ConflictError when name already exists."""
        repo = _mock_repo(
            exists_by_name_in_project=AsyncMock(return_value=True),
        )
        handler = CreateEvaluationHandler(repo)
        command = CreateEvaluationCommand(
            project_id="proj-1",
            dataset_id=None,
            name="existing",
            provider="openai",
            model="gpt-4",
            metrics=("accuracy",),
        )

        with pytest.raises(ConflictError, match="already exists"):
            await handler.handle(command)

    async def test_create_missing_provider_raises(self) -> None:
        """Handler raises ValueError when provider is missing."""
        repo = _mock_repo()
        handler = CreateEvaluationHandler(repo)
        command = CreateEvaluationCommand(
            project_id="proj-1",
            dataset_id=None,
            name="test",
            provider="",
            model="gpt-4",
            metrics=("accuracy",),
        )

        with pytest.raises(ValueError, match="cannot be empty"):
            await handler.handle(command)


class TestUpdateEvaluationHandler:
    """Tests for UpdateEvaluationHandler."""

    async def test_update_evaluation(self) -> None:
        """Handler updates and persists an evaluation."""
        evaluation = _make_evaluation()
        repo = _mock_repo(
            get_by_id=AsyncMock(return_value=evaluation),
            exists_by_name_in_project=AsyncMock(return_value=False),
            update=AsyncMock(),
        )
        handler = UpdateEvaluationHandler(repo)
        command = UpdateEvaluationCommand(
            evaluation_id=str(evaluation.id),
            name="updated-name",
        )

        result = await handler.handle(command)

        assert str(result.name.value) == "updated-name"
        repo.update.assert_called_once()

    async def test_update_not_found_raises(self) -> None:
        """Handler raises NotFoundError when evaluation not found."""
        repo = _mock_repo(get_by_id=AsyncMock(return_value=None))
        handler = UpdateEvaluationHandler(repo)
        command = UpdateEvaluationCommand(
            evaluation_id=str(UUIDv7()),
            name="test",
        )

        with pytest.raises(NotFoundError, match="not found"):
            await handler.handle(command)


class TestDeleteEvaluationHandler:
    """Tests for DeleteEvaluationHandler."""

    async def test_delete_evaluation(self) -> None:
        """Handler deletes an evaluation."""
        evaluation = _make_evaluation()
        repo = _mock_repo(
            get_by_id=AsyncMock(return_value=evaluation),
            delete=AsyncMock(return_value=True),
        )
        handler = DeleteEvaluationHandler(repo)
        command = DeleteEvaluationCommand(evaluation_id=str(evaluation.id))

        await handler.handle(command)

        repo.delete.assert_called_once()

    async def test_delete_not_found_raises(self) -> None:
        """Handler raises NotFoundError when evaluation not found."""
        repo = _mock_repo(get_by_id=AsyncMock(return_value=None))
        handler = DeleteEvaluationHandler(repo)
        command = DeleteEvaluationCommand(evaluation_id=str(UUIDv7()))

        with pytest.raises(NotFoundError, match="not found"):
            await handler.handle(command)


class TestDuplicateEvaluationHandler:
    """Tests for DuplicateEvaluationHandler."""

    async def test_duplicate_evaluation(self) -> None:
        """Handler duplicates an evaluation."""
        evaluation = _make_evaluation()
        repo = _mock_repo(
            get_by_id=AsyncMock(return_value=evaluation),
            exists_by_name_in_project=AsyncMock(return_value=False),
            create=AsyncMock(),
        )
        handler = DuplicateEvaluationHandler(repo)
        command = DuplicateEvaluationCommand(
            evaluation_id=str(evaluation.id),
            new_name="copy-eval",
        )

        result = await handler.handle(command)

        assert str(result.name.value) == "copy-eval"
        assert result.id != evaluation.id
        repo.create.assert_called_once()

    async def test_duplicate_not_found_raises(self) -> None:
        """Handler raises NotFoundError when source not found."""
        repo = _mock_repo(get_by_id=AsyncMock(return_value=None))
        handler = DuplicateEvaluationHandler(repo)
        command = DuplicateEvaluationCommand(
            evaluation_id=str(UUIDv7()),
            new_name="copy",
        )

        with pytest.raises(NotFoundError, match="not found"):
            await handler.handle(command)


class TestArchiveEvaluationHandler:
    """Tests for ArchiveEvaluationHandler."""

    async def test_archive_evaluation(self) -> None:
        """Handler archives an evaluation."""
        evaluation = _make_evaluation()
        repo = _mock_repo(
            get_by_id=AsyncMock(return_value=evaluation),
            update=AsyncMock(),
        )
        handler = ArchiveEvaluationHandler(repo)
        command = ArchiveEvaluationCommand(evaluation_id=str(evaluation.id))

        result = await handler.handle(command)

        assert result.status == EvaluationStatus.ARCHIVED
        repo.update.assert_called_once()

    async def test_archive_not_found_raises(self) -> None:
        """Handler raises NotFoundError when evaluation not found."""
        repo = _mock_repo(get_by_id=AsyncMock(return_value=None))
        handler = ArchiveEvaluationHandler(repo)
        command = ArchiveEvaluationCommand(evaluation_id=str(UUIDv7()))

        with pytest.raises(NotFoundError, match="not found"):
            await handler.handle(command)


class TestMarkReadyEvaluationHandler:
    """Tests for MarkReadyEvaluationHandler."""

    async def test_mark_ready(self) -> None:
        """Handler marks evaluation as ready."""
        evaluation = _make_evaluation()
        repo = _mock_repo(
            get_by_id=AsyncMock(return_value=evaluation),
            update=AsyncMock(),
        )
        handler = MarkReadyEvaluationHandler(repo)
        command = MarkReadyEvaluationCommand(evaluation_id=str(evaluation.id))

        result = await handler.handle(command)

        assert result.status == EvaluationStatus.READY
        repo.update.assert_called_once()


class TestGetEvaluationHandler:
    """Tests for GetEvaluationHandler."""

    async def test_get_evaluation(self) -> None:
        """Handler returns evaluation by ID."""
        evaluation = _make_evaluation()
        repo = _mock_repo(get_by_id=AsyncMock(return_value=evaluation))
        handler = GetEvaluationHandler(repo)
        query = GetEvaluationQuery(evaluation_id=str(evaluation.id))

        result = await handler.handle(query)

        assert result.id == evaluation.id

    async def test_get_not_found_raises(self) -> None:
        """Handler raises NotFoundError when not found."""
        repo = _mock_repo(get_by_id=AsyncMock(return_value=None))
        handler = GetEvaluationHandler(repo)
        query = GetEvaluationQuery(evaluation_id=str(UUIDv7()))

        with pytest.raises(NotFoundError, match="not found"):
            await handler.handle(query)


class TestListEvaluationsHandler:
    """Tests for ListEvaluationsHandler."""

    async def test_list_evaluations(self) -> None:
        """Handler returns paginated results."""
        evaluation = _make_evaluation()
        paginated = PaginatedEvaluations(
            items=[evaluation],
            total=1,
            page=1,
            page_size=20,
        )
        repo = _mock_repo(list=AsyncMock(return_value=paginated))
        handler = ListEvaluationsHandler(repo)
        query = ListEvaluationsQuery(project_id="proj-1")

        result = await handler.handle(query)

        assert result.total == 1
        assert len(result.items) == 1
