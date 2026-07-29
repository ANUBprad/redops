"""SQLAlchemy repository for Evaluation definitions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.evaluation.domain.contracts.evaluation_contracts import (
    EvaluationQuery,
    EvaluationRepository,
    PaginatedEvaluations,
)
from app.evaluation.domain.entities.evaluation_definition import Evaluation
from app.evaluation.domain.enums.evaluation_enums import EvaluationStatus
from app.evaluation.domain.value_objects.evaluation_definition_vos import (
    EvaluationDescription,
    EvaluationName,
    MetricId,
    ProviderId,
)
from app.infrastructure.database.models.evaluation import EvaluationModel
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError

try:
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:  # pragma: no cover
    pass


class SqlAlchemyEvaluationRepository(EvaluationRepository):
    """SQLAlchemy implementation of the EvaluationRepository contract.

    Maps between the domain Evaluation aggregate and the
    EvaluationModel ORM representation.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an async database session."""
        self._session = session

    async def create(self, evaluation: Evaluation) -> None:
        """Persist a new evaluation definition.

        Args:
            evaluation: The evaluation aggregate to persist.

        Raises:
            ConflictError: If a unique constraint is violated.

        """
        model = self._to_model(evaluation)
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                message=(
                    f"Evaluation with name '{evaluation.name.value}' already exists in project"
                ),
                details={
                    "project_id": evaluation.project_id,
                    "name": evaluation.name.value,
                },
            ) from exc

    async def update(self, evaluation: Evaluation) -> None:
        """Update an existing evaluation definition.

        Args:
            evaluation: The evaluation aggregate with updated values.

        """
        model = self._to_model(evaluation)
        await self._session.merge(model)

    async def delete(self, evaluation_id: UUIDv7) -> bool:
        """Delete an evaluation definition by ID.

        Args:
            evaluation_id: The UUIDv7 identifier of the evaluation.

        Returns:
            True if deleted, False if not found.

        """
        stmt = select(EvaluationModel).where(
            EvaluationModel.id == str(evaluation_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        return True

    async def get_by_id(self, evaluation_id: UUIDv7) -> Evaluation | None:
        """Find an evaluation by its ID.

        Args:
            evaluation_id: The UUIDv7 identifier.

        Returns:
            The Evaluation aggregate if found, None otherwise.

        """
        stmt = select(EvaluationModel).where(
            EvaluationModel.id == str(evaluation_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def list(self, query: EvaluationQuery) -> PaginatedEvaluations:
        """List evaluations with filtering, sorting, and pagination.

        Args:
            query: Query parameters for filtering and pagination.

        Returns:
            Paginated list of evaluations.

        """
        stmt = select(EvaluationModel)
        count_stmt = select(func.count()).select_from(EvaluationModel)

        # Apply filters
        if query.project_id is not None:
            stmt = stmt.where(EvaluationModel.project_id == query.project_id)
            count_stmt = count_stmt.where(
                EvaluationModel.project_id == query.project_id,
            )
        if query.provider is not None:
            stmt = stmt.where(EvaluationModel.provider == query.provider)
            count_stmt = count_stmt.where(
                EvaluationModel.provider == query.provider,
            )
        if query.model is not None:
            stmt = stmt.where(EvaluationModel.model == query.model)
            count_stmt = count_stmt.where(EvaluationModel.model == query.model)
        if query.status is not None:
            stmt = stmt.where(EvaluationModel.status == query.status.value)
            count_stmt = count_stmt.where(
                EvaluationModel.status == query.status.value,
            )
        if query.search is not None:
            search_pattern = f"%{query.search}%"
            search_filter = EvaluationModel.name.ilike(
                search_pattern,
            ) | EvaluationModel.description.ilike(search_pattern)
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        # Get total count
        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()

        # Apply sorting
        sort_column = _get_sort_column(query.sort_by)
        if query.sort_order == "desc":
            stmt = stmt.order_by(sort_column.desc())
        else:
            stmt = stmt.order_by(sort_column.asc())

        # Apply pagination
        offset = (query.page - 1) * query.page_size
        stmt = stmt.offset(offset).limit(query.page_size)

        # Execute
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())

        return PaginatedEvaluations(
            items=[self._to_domain(m) for m in models],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def exists(self, evaluation_id: UUIDv7) -> bool:
        """Check whether an evaluation exists.

        Args:
            evaluation_id: The UUIDv7 identifier.

        Returns:
            True if the evaluation exists, False otherwise.

        """
        stmt = select(EvaluationModel.id).where(
            EvaluationModel.id == str(evaluation_id),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def exists_by_name_in_project(
        self,
        project_id: str,
        name: str,
        exclude_id: UUIDv7 | None = None,
    ) -> bool:
        """Check whether an evaluation with the given name exists in a project.

        Args:
            project_id: The project identifier.
            name: The evaluation name to check.
            exclude_id: Optional ID to exclude from the check.

        Returns:
            True if a conflicting name exists, False otherwise.

        """
        stmt = select(EvaluationModel.id).where(
            EvaluationModel.project_id == project_id,
            EvaluationModel.name == name,
        )
        if exclude_id is not None:
            stmt = stmt.where(EvaluationModel.id != str(exclude_id))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    @staticmethod
    def _to_model(evaluation: Evaluation) -> EvaluationModel:
        """Convert a domain Evaluation to an ORM model.

        Args:
            evaluation: The domain aggregate.

        Returns:
            The corresponding ORM model.

        """
        return EvaluationModel(
            id=str(evaluation.id),
            project_id=evaluation.project_id,
            dataset_id=evaluation.dataset_id,
            name=str(evaluation.name.value),
            description=evaluation.description.value
            if evaluation.description is not None
            else None,
            provider=str(evaluation.provider.value),
            model=evaluation.model,
            metrics=[m.value for m in evaluation.metrics],
            tags=list(evaluation.tags),
            configuration=dict(evaluation.configuration),
            status=evaluation.status.value,
            created_by=evaluation.created_by,
            version=evaluation.version,
            created_at=evaluation.created_at,
            updated_at=evaluation.updated_at,
        )

    @staticmethod
    def _to_domain(model: EvaluationModel) -> Evaluation:
        """Convert an ORM model to a domain Evaluation.

        Args:
            model: The ORM model.

        Returns:
            The corresponding domain aggregate.

        """
        return Evaluation(
            entity_id=UUIDv7.from_string(model.id),
            project_id=model.project_id,
            dataset_id=model.dataset_id,
            name=EvaluationName(value=model.name),
            description=EvaluationDescription(value=model.description)
            if model.description is not None
            else None,
            provider=ProviderId(value=model.provider),
            model=model.model,
            metrics=tuple(MetricId(value=m) for m in model.metrics),
            tags=tuple(model.tags),
            configuration=model.configuration,
            status=EvaluationStatus(model.status),
            created_by=model.created_by,
        )


def _get_sort_column(sort_by: str) -> Any:
    """Map a sort field name to the corresponding ORM column.

    Args:
        sort_by: The field name to sort by.

    Returns:
        The corresponding SQLAlchemy column.

    """
    columns: dict[str, Any] = {
        "created_at": EvaluationModel.created_at,
        "updated_at": EvaluationModel.updated_at,
        "name": EvaluationModel.name,
    }
    return columns.get(sort_by, EvaluationModel.created_at)
