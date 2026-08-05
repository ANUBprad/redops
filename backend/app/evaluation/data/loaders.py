"""Dataset loaders.

Loaders turn raw sources (files, dicts) into EvaluationDataset
instances. A dataset loader is the boundary through which real
evaluation content enters the platform.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from app.evaluation.data.dataset import DatasetItem, EvaluationDataset

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = [
    "DatasetLoadError",
    "DatasetLoader",
    "DictDatasetLoader",
    "JsonDatasetLoader",
    "JsonlDatasetLoader",
    "dataset_from_items",
]


class DatasetLoadError(ValueError):
    """Raised when a dataset cannot be loaded from a source."""


@runtime_checkable
class DatasetLoader(Protocol):
    """Contract for dataset loaders.

    Implementations convert a source (e.g. a file path or raw
    payload) into an EvaluationDataset.
    """

    async def load(self, source: str) -> EvaluationDataset:
        """Load a dataset from the given source."""
        ...


def dataset_from_items(
    items: Sequence[Mapping[str, Any]],
    *,
    name: str = "dataset",
    version: str = "1.0.0",
) -> EvaluationDataset:
    """Build an EvaluationDataset from a sequence of item dicts.

    Args:
        items: Sequence of item mappings (each must contain a prompt).
        name: Dataset name.
        version: Dataset version.

    Returns:
        A new EvaluationDataset.

    Raises:
        DatasetLoadError: If any item is invalid.

    """
    try:
        parsed = tuple(DatasetItem.from_dict(item) for item in items)
    except ValueError as exc:
        raise DatasetLoadError(str(exc)) from exc
    return EvaluationDataset(name=name, items=parsed, version=version)


class DictDatasetLoader:
    """Loads a dataset from an in-memory list of item dicts.

    Usage:
        loader = DictDatasetLoader([{"prompt": "..."}, ...])
        dataset = await loader.load("")
    """

    def __init__(
        self,
        items: Sequence[Mapping[str, Any]],
        *,
        name: str = "in-memory",
        version: str = "1.0.0",
    ) -> None:
        """Initialize with the raw items.

        Args:
            items: Sequence of item mappings.
            name: Dataset name.
            version: Dataset version.

        """
        self._items = items
        self._name = name
        self._version = version

    async def load(self, source: str = "") -> EvaluationDataset:
        """Return the dataset built from the provided items.

        Args:
            source: Ignored; kept for protocol compatibility.

        Returns:
            The in-memory dataset.

        """
        return dataset_from_items(
            self._items,
            name=self._name,
            version=self._version,
        )


class JsonlDatasetLoader:
    """Loads a dataset from a JSONL file.

    Each non-empty line must be a JSON object with at least a
    ``prompt`` key. Optional keys: ``id``, ``reference``,
    ``context``, ``metadata``.
    """

    def __init__(self, *, name: str = "jsonl-dataset") -> None:
        """Initialize the loader.

        Args:
            name: Dataset name used when the file has no header.

        """
        self._name = name

    async def load(self, source: str) -> EvaluationDataset:
        """Load a dataset from a JSONL file.

        Args:
            source: Path to the JSONL file.

        Returns:
            The loaded dataset.

        Raises:
            DatasetLoadError: If the file cannot be parsed.

        """
        raw_lines = await asyncio.to_thread(self._read_lines, source)
        items: list[Mapping[str, Any]] = []
        for line_number, line in enumerate(raw_lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                msg = f"Invalid JSON on line {line_number}: {exc}"
                raise DatasetLoadError(msg) from exc
            if not isinstance(parsed, dict):
                msg = f"Line {line_number} must be a JSON object"
                raise DatasetLoadError(msg)
            items.append(parsed)
        return dataset_from_items(items, name=self._name)

    @staticmethod
    def _read_lines(path: str) -> list[str]:
        """Read all non-empty lines from a file."""
        with open(path, encoding="utf-8") as handle:
            return handle.read().splitlines()


class JsonDatasetLoader:
    """Loads a dataset from a JSON file.

    Supports either a top-level object with ``name``/``items`` keys
    or a bare array of item objects.
    """

    def __init__(self, *, name: str = "json-dataset") -> None:
        """Initialize the loader.

        Args:
            name: Dataset name used when the JSON has no name key.

        """
        self._name = name

    async def load(self, source: str) -> EvaluationDataset:
        """Load a dataset from a JSON file.

        Args:
            source: Path to the JSON file.

        Returns:
            The loaded dataset.

        Raises:
            DatasetLoadError: If the file cannot be parsed.

        """
        raw = await asyncio.to_thread(self._read_json, source)
        if isinstance(raw, list):
            return dataset_from_items(raw, name=self._name)
        if isinstance(raw, dict):
            try:
                return EvaluationDataset.from_dict(raw)
            except ValueError as exc:
                raise DatasetLoadError(str(exc)) from exc
        msg = "JSON dataset must be an array or an object with 'items'"
        raise DatasetLoadError(msg)

    @staticmethod
    def _read_json(path: str) -> Any:
        """Read and parse a JSON file."""
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
