"""Repository contracts for the Red Team domain."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.kernel.entities.base import UUIDv7
    from app.redteam.domain.entities import AttackDefinition, AttackRun
    from app.redteam.domain.enums import (
        AttackCategory,
        AttackDefinitionStatus,
        AttackSeverity,
        AttackStatus,
    )


@dataclass
class AttackDefinitionQuery:
    category: AttackCategory | None = None
    severity: AttackSeverity | None = None
    status: AttackDefinitionStatus | None = None
    search: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20


@dataclass
class PaginatedAttackDefinitions:
    items: list[AttackDefinition] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)


@dataclass
class AttackRunQuery:
    status: AttackStatus | None = None
    evaluation_run_id: str | None = None
    category: AttackCategory | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20


@dataclass
class PaginatedAttackRuns:
    items: list[AttackRun] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)


class AttackDefinitionRepository(ABC):
    @abstractmethod
    async def save(self, definition: AttackDefinition) -> None: ...

    @abstractmethod
    async def find_by_id(self, definition_id: UUIDv7) -> AttackDefinition | None: ...

    @abstractmethod
    async def list(self, query: AttackDefinitionQuery) -> PaginatedAttackDefinitions: ...

    @abstractmethod
    async def delete(self, definition_id: UUIDv7) -> bool: ...

    @abstractmethod
    async def exists(self, definition_id: UUIDv7) -> bool: ...


class AttackRunRepository(ABC):
    @abstractmethod
    async def save(self, run: AttackRun) -> None: ...

    @abstractmethod
    async def find_by_id(self, run_id: UUIDv7) -> AttackRun | None: ...

    @abstractmethod
    async def list(self, query: AttackRunQuery) -> PaginatedAttackRuns: ...

    @abstractmethod
    async def exists(self, run_id: UUIDv7) -> bool: ...

    @abstractmethod
    async def persist_progress(self, run: AttackRun) -> None: ...

    @abstractmethod
    async def find_by_date_range(
        self,
        since: datetime,
        until: datetime,
    ) -> Sequence[AttackRun]:
        """Find attack runs created within a date range."""
        ...
