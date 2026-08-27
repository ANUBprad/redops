"""SQLAlchemy repository for Experiment persistence."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.evaluation.domain.contracts.experiment_contracts import (
    ExperimentQuery,
    ExperimentRepository,
    PaginatedExperiments,
)
from app.evaluation.domain.entities.experiment import Experiment
from app.evaluation.domain.enums.experiment_enums import ExperimentStatus
from app.evaluation.domain.value_objects.experiment_value_objects import (
    ExperimentDescription,
    ExperimentName,
)
from app.infrastructure.database.models.experiment import ExperimentModel
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError

try:
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:  # pragma: no cover
    pass


class SqlAlchemyExperimentRepository(ExperimentRepository):
    """SQLAlchemy implementation of the ExperimentRepository contract."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an async database session."""
        self._session = session

    async def save(self, experiment: Experiment) -> None:
        """Persist an experiment (create or update)."""
        model = self._to_model(experiment)
        await self._session.merge(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                message=f"Experiment {experiment.id} failed to persist",
                details={"experiment_id": str(experiment.id)},
            ) from exc

    async def find_by_id(self, experiment_id: UUIDv7) -> Experiment | None:
        """Find an experiment by its ID."""
        stmt = select(ExperimentModel).where(ExperimentModel.id == str(experiment_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def list(self, query: ExperimentQuery) -> PaginatedExperiments:
        """List experiments with filtering, sorting, and pagination."""
        stmt = select(ExperimentModel)

        if query.project_id is not None:
            stmt = stmt.where(ExperimentModel.project_id == query.project_id)
        if query.status is not None:
            stmt = stmt.where(ExperimentModel.status == query.status.value)
        if query.search:
            stmt = stmt.where(ExperimentModel.name.ilike(f"%{query.search}%"))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        sort_col = getattr(ExperimentModel, query.sort_by, ExperimentModel.created_at)
        if query.sort_order == "desc":
            stmt = stmt.order_by(sort_col.desc())
        else:
            stmt = stmt.order_by(sort_col.asc())

        offset = (query.page - 1) * query.page_size
        stmt = stmt.offset(offset).limit(query.page_size)

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return PaginatedExperiments(
            items=[self._to_entity(m) for m in models],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def delete(self, experiment_id: UUIDv7) -> bool:
        """Delete an experiment by ID."""
        stmt = select(ExperimentModel).where(ExperimentModel.id == str(experiment_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    async def exists_by_name_in_project(
        self,
        project_id: str,
        name: str,
        exclude_id: UUIDv7 | None = None,
    ) -> bool:
        """Check whether an experiment with the given name exists in a project."""
        stmt = select(func.count()).where(
            ExperimentModel.project_id == project_id,
            ExperimentModel.name == name,
        )
        if exclude_id is not None:
            stmt = stmt.where(ExperimentModel.id != str(exclude_id))
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    def _to_model(self, experiment: Experiment) -> ExperimentModel:
        """Convert domain entity to ORM model."""
        return ExperimentModel(
            id=str(experiment.id),
            project_id=experiment.project_id,
            name=str(experiment.name.value),
            description=experiment.description.value if experiment.description else None,
            hypothesis=experiment.hypothesis,
            status=experiment.status.value,
            baseline_run_id=experiment.baseline_run_id,
            conclusion=experiment.conclusion,
            tags=list(experiment.tags),
            created_by=experiment.created_by,
            version=experiment.version,
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
        )

    def _to_entity(self, model: ExperimentModel) -> Experiment:
        """Convert ORM model to domain entity."""
        return Experiment(
            entity_id=UUIDv7.from_string(model.id),
            project_id=model.project_id,
            name=ExperimentName(value=model.name),
            description=(
                ExperimentDescription(value=model.description) if model.description else None
            ),
            hypothesis=model.hypothesis,
            status=ExperimentStatus(model.status),
            baseline_run_id=model.baseline_run_id,
            conclusion=model.conclusion,
            tags=tuple(model.tags) if model.tags else (),
            created_by=model.created_by,
        )
