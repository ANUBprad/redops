from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from app.kernel.entities.base import UUIDv7
from app.kernel.results.result import Result
from app.kernel.exceptions.errors import NotFoundError

TEntity = TypeVar("TEntity")


@dataclass
class QueryOptions:
    page: int = 1
    page_size: int = 20
    sort_by: str | None = None
    sort_order: str = "asc"
    filters: dict[str, Any] = field(default_factory=dict)


class ReadRepository(ABC, Generic[TEntity]):
    @abstractmethod
    async def find_by_id(self, entity_id: UUIDv7) -> Result[TEntity, NotFoundError]:
        ...

    @abstractmethod
    async def exists(self, entity_id: UUIDv7) -> bool:
        ...

    @abstractmethod
    async def count(self, **filters: object) -> int:
        ...


class WriteRepository(ABC, Generic[TEntity]):
    @abstractmethod
    async def add(self, entity: TEntity) -> None:
        ...

    @abstractmethod
    async def update(self, entity: TEntity) -> None:
        ...

    @abstractmethod
    async def delete(self, entity_id: UUIDv7) -> Result[None, NotFoundError]:
        ...


class Repository(ReadRepository[TEntity], WriteRepository[TEntity], ABC):
    ...
