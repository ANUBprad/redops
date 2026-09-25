"""SQLAlchemy repository for EvaluationProfile persistence."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.evaluation.domain.contracts.profile_contracts import (
    PaginatedProfiles,
    ProfileQuery,
    ProfileRepository,
)
from app.evaluation.domain.entities.profile import EvaluationProfileEntity
from app.evaluation.domain.enums.profile_enums import ProfileScope
from app.evaluation.domain.value_objects.profile_value_objects import (
    ProfileDescription,
    ProfileName,
)
from app.infrastructure.database.models.evaluation_profile import EvaluationProfileModel
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError

try:
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:  # pragma: no cover
    pass


class SqlAlchemyProfileRepository(ProfileRepository):
    """SQLAlchemy implementation of the ProfileRepository contract."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an async database session."""
        self._session = session

    async def save(self, profile: EvaluationProfileEntity) -> None:
        """Persist a profile (create or update)."""
        model = self._to_model(profile)
        await self._session.merge(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                message=f"Profile {profile.id} failed to persist",
                details={"profile_id": str(profile.id)},
            ) from exc

    async def find_by_id(self, profile_id: UUIDv7) -> EvaluationProfileEntity | None:
        """Find a profile by its ID."""
        stmt = select(EvaluationProfileModel).where(EvaluationProfileModel.id == str(profile_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def list(self, query: ProfileQuery) -> PaginatedProfiles:
        """List profiles with filtering, sorting, and pagination."""
        stmt = select(EvaluationProfileModel)

        if query.project_id is not None:
            stmt = stmt.where(EvaluationProfileModel.project_id == query.project_id)
        if query.is_builtin is not None:
            stmt = stmt.where(EvaluationProfileModel.is_builtin == query.is_builtin)
        if query.search:
            stmt = stmt.where(EvaluationProfileModel.name.ilike(f"%{query.search}%"))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        sort_col = getattr(EvaluationProfileModel, query.sort_by, EvaluationProfileModel.created_at)
        if query.sort_order == "desc":
            stmt = stmt.order_by(sort_col.desc())
        else:
            stmt = stmt.order_by(sort_col.asc())

        offset = (query.page - 1) * query.page_size
        stmt = stmt.offset(offset).limit(query.page_size)

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return PaginatedProfiles(
            items=[self._to_entity(m) for m in models],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def delete(self, profile_id: UUIDv7) -> bool:
        """Delete a profile by ID."""
        stmt = select(EvaluationProfileModel).where(EvaluationProfileModel.id == str(profile_id))
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
        """Check whether a profile with the given name exists in a project."""
        stmt = select(func.count()).where(
            EvaluationProfileModel.project_id == project_id,
            EvaluationProfileModel.name == name,
        )
        if exclude_id is not None:
            stmt = stmt.where(EvaluationProfileModel.id != str(exclude_id))
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    def _to_model(self, profile: EvaluationProfileEntity) -> EvaluationProfileModel:
        """Convert domain entity to ORM model."""
        return EvaluationProfileModel(
            id=str(profile.id),
            project_id=profile.project_id,
            name=str(profile.name.value),
            description=profile.description.value if profile.description else None,
            scope=profile.scope.value,
            configuration=profile.configuration,
            is_builtin=profile.is_builtin,
            version=profile.version,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    def _to_entity(self, model: EvaluationProfileModel) -> EvaluationProfileEntity:
        """Convert ORM model to domain entity."""
        return EvaluationProfileEntity(
            entity_id=UUIDv7.from_string(model.id),
            project_id=model.project_id,
            name=ProfileName(value=model.name),
            description=(
                ProfileDescription(value=model.description) if model.description else None
            ),
            scope=ProfileScope(model.scope),
            configuration=model.configuration,
            is_builtin=model.is_builtin,
        )
