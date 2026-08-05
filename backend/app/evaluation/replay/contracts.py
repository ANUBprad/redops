"""Repository contract for execution trace persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class TraceRepository(ABC):
    """Abstract repository for execution trace storage."""

    @abstractmethod
    async def find_by_run_id(self, run_id: str) -> dict[str, Any] | None:
        """Find a trace by run ID."""

    @abstractmethod
    async def save(self, run_id: str, trace_data: dict[str, Any]) -> None:
        """Save a trace for a run."""

    @abstractmethod
    async def delete(self, run_id: str) -> bool:
        """Delete a trace by run ID."""

    @abstractmethod
    async def list_runs(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """List stored traces."""
