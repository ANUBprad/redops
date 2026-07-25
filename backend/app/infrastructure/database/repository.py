"""Generic SQLAlchemy repository implementing Kernel Repository contracts.

Provides a reusable base for building type-safe repository implementations
that satisfy the Kernel's Repository, ReadRepository, and WriteRepository
interfaces. Concrete entity repositories extend this class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from sqlalchemy import func, select

from app.kernel.exceptions.errors import NotFoundError
from app.kernel.repositories.repository import Repository
from app.kernel.results.result import Result, failure, success

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.kernel.entities.base import UUIDv7

TEntity = TypeVar("TEntity")


class SqlAlchemyRepository[TEntity](Repository[TEntity]):
    """Generic SQLAlchemy repository implementing the Kernel Repository interface.

    Operates directly on SQLAlchemy ORM models. Concrete repositories
    for specific entity types should extend this class, providing the
    model class and optional mapper functions.

    Type Parameters:
        TEntity: The entity type, typically a SQLAlchemy ORM model.

    """

    def __init__(self, session: AsyncSession, model_class: type[Any]) -> None:
        """Initialize with session and model class."""
        self._session = session
        self._model_class = model_class

    async def find_by_id(self, entity_id: UUIDv7) -> Result[TEntity, NotFoundError]:
        """Find an entity by its UUIDv7 identifier.

        Args:
            entity_id: The UUIDv7 identifier of the entity.

        Returns:
            Success containing the entity if found, or Failure with NotFoundError.

        """
        stmt = select(self._model_class).where(
            self._model_class.id == entity_id.value,
        )
        result = await self._session.execute(stmt)
        model: TEntity | None = result.scalar_one_or_none()
        if model is None:
            return failure(
                NotFoundError(
                    message=f"{self._model_class.__name__} not found: {entity_id}",
                    resource_type=self._model_class.__name__,
                    resource_id=str(entity_id),
                ),
            )
        return success(model)

    async def exists(self, entity_id: UUIDv7) -> bool:
        """Check whether an entity with the given ID exists.

        Args:
            entity_id: The UUIDv7 identifier to check.

        Returns:
            True if the entity exists, False otherwise.

        """
        stmt = select(self._model_class).where(
            self._model_class.id == entity_id.value,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def count(self, **filters: object) -> int:
        """Count entities matching the given filters.

        Args:
            **filters: Keyword arguments mapping field names to filter values.

        Returns:
            The count of matching entities.

        """
        stmt = select(func.count()).select_from(self._model_class)
        for field, value in filters.items():
            column = getattr(self._model_class, field, None)
            if column is not None:
                stmt = stmt.where(column == value)
        result = await self._session.execute(stmt)
        count_value: int = result.scalar_one()
        return count_value

    async def add(self, entity: TEntity) -> None:
        """Add a new entity to the repository.

        Args:
            entity: The entity to add. Must be an instance of the model class.

        """
        self._session.add(entity)

    async def update(self, entity: TEntity) -> None:
        """Update an existing entity in the repository.

        Args:
            entity: The entity with updated values.

        """
        await self._session.merge(entity)

    async def delete(self, entity_id: UUIDv7) -> Result[None, NotFoundError]:
        """Delete an entity by its UUIDv7 identifier.

        Args:
            entity_id: The UUIDv7 identifier of the entity to delete.

        Returns:
            Success(None) if deleted, or Failure with NotFoundError.

        """
        stmt = select(self._model_class).where(
            self._model_class.id == entity_id.value,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return failure(
                NotFoundError(
                    message=f"{self._model_class.__name__} not found: {entity_id}",
                    resource_type=self._model_class.__name__,
                    resource_id=str(entity_id),
                ),
            )
        await self._session.delete(model)
        return success(None)
