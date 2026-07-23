from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PageParams:
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


@dataclass(frozen=True)
class CursorParams(Generic[T]):
    cursor: str | None = None
    page_size: int = 20
    sort_by: str = "created_at"
    sort_order: str = "desc"


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_next: bool = False
    has_previous: bool = False

    @property
    def total_pages(self) -> int:
        if self.page_size == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


@dataclass(frozen=True)
class CursorPage(Generic[T]):
    items: list[T] = field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False


class Paginator(ABC, Generic[T]):
    @abstractmethod
    async def paginate(self, params: PageParams) -> Page[T]:
        ...

    @abstractmethod
    async def count(self) -> int:
        ...


class CursorPaginator(ABC, Generic[T]):
    @abstractmethod
    async def paginate(self, params: CursorParams[T]) -> CursorPage[T]:
        ...

    @abstractmethod
    async def has_next(self, cursor: str | None) -> bool:
        ...
