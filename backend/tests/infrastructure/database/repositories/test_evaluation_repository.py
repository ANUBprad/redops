"""Tests for SqlAlchemyEvaluationRepository."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.evaluation.domain.contracts.evaluation_contracts import EvaluationQuery
from app.evaluation.domain.entities.evaluation_definition import Evaluation
from app.evaluation.domain.value_objects.evaluation_definition_vos import (
    EvaluationName,
    MetricId,
    ProviderId,
)
from app.infrastructure.database.models.evaluation import EvaluationModel
from app.infrastructure.database.repositories.evaluation_repository import (
    SqlAlchemyEvaluationRepository,
)
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError


def _make_evaluation(
    *,
    name: str = "test-eval",
    project_id: str = "proj-1",
) -> Evaluation:
    """Create a minimal Evaluation for testing."""
    return Evaluation.create(
        project_id=project_id,
        dataset_id="ds-1",
        name=EvaluationName(value=name),
        provider=ProviderId(value="openai"),
        model="gpt-4",
        metrics=(MetricId(value="accuracy"),),
    )


def _make_model(*, eval_id: str | None = None, name: str = "test-eval") -> EvaluationModel:
    """Create a minimal EvaluationModel for testing."""
    return EvaluationModel(
        id=eval_id or str(UUIDv7()),
        project_id="proj-1",
        dataset_id="ds-1",
        name=name,
        description=None,
        provider="openai",
        model="gpt-4",
        metrics=["accuracy"],
        tags=[],
        configuration={},
        status="draft",
        created_by=None,
        version=1,
    )


def _mock_scalar_result(value: object) -> MagicMock:
    """Create a mock scalar result."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_scalars_result(values: list[object]) -> MagicMock:
    """Create a mock scalars result for list queries."""
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = values
    result.scalars.return_value = scalars
    return result


class TestSqlAlchemyEvaluationRepositoryCreate:
    """Tests for repository create method."""

    async def test_create_adds_to_session(self) -> None:
        """Create adds the model to the session."""
        session = AsyncMock()
        repo = SqlAlchemyEvaluationRepository(session)
        evaluation = _make_evaluation()

        await repo.create(evaluation)

        session.add.assert_called_once()
        added_model = session.add.call_args[0][0]
        assert isinstance(added_model, EvaluationModel)
        assert added_model.name == "test-eval"
        assert added_model.status == "draft"

    async def test_create_integrity_error_raises_conflict(self) -> None:
        """Create translates IntegrityError to ConflictError."""
        from sqlalchemy.exc import IntegrityError

        session = AsyncMock()
        flush_error = IntegrityError("INSERT", (), Exception("unique violation"))
        session.flush = AsyncMock(side_effect=flush_error)
        repo = SqlAlchemyEvaluationRepository(session)
        evaluation = _make_evaluation()

        with pytest.raises(ConflictError, match="already exists"):
            await repo.create(evaluation)


class TestSqlAlchemyEvaluationRepositoryGetById:
    """Tests for repository get_by_id method."""

    async def test_get_by_id_found(self) -> None:
        """Get by ID returns evaluation when found."""
        session = AsyncMock()
        model = _make_model()
        session.execute = AsyncMock(return_value=_mock_scalar_result(model))

        repo = SqlAlchemyEvaluationRepository(session)
        ev_id = UUIDv7.from_string(model.id)
        result = await repo.get_by_id(ev_id)

        assert result is not None
        assert str(result.id) == model.id
        assert str(result.name.value) == "test-eval"

    async def test_get_by_id_not_found(self) -> None:
        """Get by ID returns None when not found."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_mock_scalar_result(None))

        repo = SqlAlchemyEvaluationRepository(session)
        result = await repo.get_by_id(UUIDv7())

        assert result is None


class TestSqlAlchemyEvaluationRepositoryUpdate:
    """Tests for repository update method."""

    async def test_update_merges_model(self) -> None:
        """Update merges the model into the session."""
        session = AsyncMock()
        repo = SqlAlchemyEvaluationRepository(session)
        evaluation = _make_evaluation()

        await repo.update(evaluation)

        session.merge.assert_called_once()
        merged_model = session.merge.call_args[0][0]
        assert isinstance(merged_model, EvaluationModel)


class TestSqlAlchemyEvaluationRepositoryDelete:
    """Tests for repository delete method."""

    async def test_delete_removes_model(self) -> None:
        """Delete removes the model from the session."""
        session = AsyncMock()
        model = _make_model()
        session.execute = AsyncMock(return_value=_mock_scalar_result(model))

        repo = SqlAlchemyEvaluationRepository(session)
        ev_id = UUIDv7.from_string(model.id)
        result = await repo.delete(ev_id)

        assert result is True
        session.delete.assert_called_once_with(model)

    async def test_delete_not_found(self) -> None:
        """Delete returns False when not found."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_mock_scalar_result(None))

        repo = SqlAlchemyEvaluationRepository(session)
        result = await repo.delete(UUIDv7())

        assert result is False


class TestSqlAlchemyEvaluationRepositoryExists:
    """Tests for repository exists method."""

    async def test_exists_true(self) -> None:
        """Exists returns True when found."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_mock_scalar_result("id"))

        repo = SqlAlchemyEvaluationRepository(session)
        result = await repo.exists(UUIDv7())

        assert result is True

    async def test_exists_false(self) -> None:
        """Exists returns False when not found."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_mock_scalar_result(None))

        repo = SqlAlchemyEvaluationRepository(session)
        result = await repo.exists(UUIDv7())

        assert result is False


class TestSqlAlchemyEvaluationRepositoryExistsByNameInProject:
    """Tests for repository exists_by_name_in_project method."""

    async def test_exists_by_name_true(self) -> None:
        """Returns True when name exists in project."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_mock_scalar_result("id"))

        repo = SqlAlchemyEvaluationRepository(session)
        result = await repo.exists_by_name_in_project("proj-1", "test-eval")

        assert result is True

    async def test_exists_by_name_false(self) -> None:
        """Returns False when name does not exist."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_mock_scalar_result(None))

        repo = SqlAlchemyEvaluationRepository(session)
        result = await repo.exists_by_name_in_project("proj-1", "unique")

        assert result is False

    async def test_exists_by_name_excludes_id(self) -> None:
        """Excludes the specified ID from the check."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_mock_scalar_result(None))

        repo = SqlAlchemyEvaluationRepository(session)
        exclude_id = UUIDv7()
        result = await repo.exists_by_name_in_project(
            "proj-1",
            "test-eval",
            exclude_id=exclude_id,
        )

        assert result is False


class TestSqlAlchemyEvaluationRepositoryList:
    """Tests for repository list method."""

    async def test_list_returns_paginated_results(self) -> None:
        """List returns paginated results."""
        session = AsyncMock()
        model = _make_model()

        # Mock count query
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1

        # Mock select query
        select_result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = [model]
        select_result.scalars.return_value = scalars

        session.execute = AsyncMock(side_effect=[count_result, select_result])

        repo = SqlAlchemyEvaluationRepository(session)
        query = EvaluationQuery(project_id="proj-1", page=1, page_size=10)
        result = await repo.list(query)

        assert result.total == 1
        assert len(result.items) == 1
        assert result.page == 1
        assert result.page_size == 10
