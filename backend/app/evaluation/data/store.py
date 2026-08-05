"""Dataset store — persists and resolves evaluation datasets by ID.

A dataset store lets evaluations reference a dataset by ID via
DatasetReference while keeping the actual items out of the run
entity. The in-memory implementation supports the direct
pipeline path and tests.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from app.evaluation.data.dataset import EvaluationDataset

__all__ = [
    "DatasetNotFoundError",
    "DatasetStore",
    "InMemoryDatasetStore",
]


class DatasetNotFoundError(KeyError):
    """Raised when a dataset ID is unknown to the store."""


@runtime_checkable
class DatasetStore(Protocol):
    """Contract for storing and retrieving datasets by ID."""

    async def save(
        self,
        dataset: EvaluationDataset,
        *,
        dataset_id: str | None = None,
    ) -> str:
        """Persist a dataset and return its ID."""
        ...

    async def load(self, dataset_id: str) -> EvaluationDataset:
        """Load a dataset by ID.

        Raises:
            DatasetNotFoundError: If the ID is unknown.

        """
        ...

    async def delete(self, dataset_id: str) -> None:
        """Remove a dataset by ID."""
        ...

    def list_ids(self) -> list[str]:
        """Return all stored dataset IDs."""
        ...


class InMemoryDatasetStore:
    """In-memory dataset store.

    Suitable for tests and single-process deployments. Datasets
    are kept in a dict keyed by dataset ID.
    """

    def __init__(
        self,
        datasets: Mapping[str, EvaluationDataset] | None = None,
    ) -> None:
        """Initialize the store.

        Args:
            datasets: Optional pre-populated datasets by ID.

        """
        self._datasets: dict[str, EvaluationDataset] = dict(datasets or {})

    async def save(
        self,
        dataset: EvaluationDataset,
        *,
        dataset_id: str | None = None,
    ) -> str:
        """Persist a dataset and return its ID.

        Args:
            dataset: The dataset to store.
            dataset_id: Optional explicit ID; defaults to a new UUID.

        Returns:
            The dataset ID.

        """
        resolved_id = dataset_id or str(uuid.uuid4())
        self._datasets[resolved_id] = dataset
        return resolved_id

    async def load(self, dataset_id: str) -> EvaluationDataset:
        """Load a dataset by ID.

        Args:
            dataset_id: The dataset ID.

        Returns:
            The stored dataset.

        Raises:
            DatasetNotFoundError: If the ID is unknown.

        """
        try:
            return self._datasets[dataset_id]
        except KeyError as exc:
            raise DatasetNotFoundError(dataset_id) from exc

    async def delete(self, dataset_id: str) -> None:
        """Remove a dataset by ID.

        Args:
            dataset_id: The dataset ID to remove.

        """
        self._datasets.pop(dataset_id, None)

    def list_ids(self) -> list[str]:
        """Return all stored dataset IDs."""
        return list(self._datasets)
