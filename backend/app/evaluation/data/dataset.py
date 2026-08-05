"""Dataset item and evaluation dataset domain objects.

The dataset is the real input to an evaluation run. Each item
carries the prompt sent to the provider plus optional reference
outputs and context used by metric evaluators.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class DatasetItem:
    """A single evaluation sample.

    Attributes:
        prompt: The prompt sent to the provider.
        reference: Optional reference answer used by reference-based metrics.
        context: Optional context provided to the model (e.g. RAG passages).
        id: Optional stable identifier for the item.
        metadata: Arbitrary string metadata attached to the item.

    """

    prompt: str
    reference: str | None = None
    context: str | None = None
    id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate item invariants."""
        if not self.prompt:
            msg = "Dataset item prompt cannot be empty"
            raise ValueError(msg)

    def to_variables(self) -> dict[str, str]:
        """Return template variables available when rendering this item.

        Metadata keys are merged last so they can override the
        reserved keys (prompt, reference, context, id).

        Returns:
            A mapping of variable name to string value.

        """
        variables: dict[str, str] = {
            "prompt": self.prompt,
            "reference": self.reference or "",
            "context": self.context or "",
            "id": self.id or "",
        }
        variables.update(self.metadata)
        return variables

    def to_dict(self) -> dict[str, Any]:
        """Serialize the item to a plain dict.

        Returns:
            A JSON-serializable representation.

        """
        return {
            "id": self.id,
            "prompt": self.prompt,
            "reference": self.reference,
            "context": self.context,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DatasetItem:
        """Create a dataset item from a dict.

        Args:
            data: Mapping with ``prompt`` (required) and optional
                ``id``, ``reference``, ``context``, ``metadata``.

        Returns:
            A new DatasetItem instance.

        """
        prompt = data.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            msg = "Dataset item requires a non-empty 'prompt' string"
            raise ValueError(msg)
        raw_metadata = data.get("metadata") or {}
        metadata = {str(key): str(value) for key, value in raw_metadata.items()}
        return cls(
            prompt=prompt,
            reference=_optional_str(data.get("reference")),
            context=_optional_str(data.get("context")),
            id=_optional_str(data.get("id")),
            metadata=metadata,
        )


@dataclass(frozen=True, slots=True)
class EvaluationDataset:
    """An ordered collection of evaluation items.

    Attributes:
        name: Human-readable dataset name.
        items: The items in evaluation order.
        version: Dataset version identifier.
        description: Optional human-readable description.

    """

    name: str
    items: tuple[DatasetItem, ...]
    version: str = "1.0.0"
    description: str | None = None

    def __post_init__(self) -> None:
        """Validate dataset invariants."""
        if not self.name:
            msg = "Dataset name cannot be empty"
            raise ValueError(msg)

    @property
    def item_count(self) -> int:
        """Return the number of items in the dataset."""
        return len(self.items)

    def item(self, index: int) -> DatasetItem:
        """Return the item at the given index.

        Args:
            index: Zero-based item index.

        Returns:
            The dataset item.

        Raises:
            IndexError: If the index is out of range.

        """
        return self.items[index]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the dataset to a plain dict.

        Returns:
            A JSON-serializable representation.

        """
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EvaluationDataset:
        """Create a dataset from a dict.

        Args:
            data: Mapping with ``name`` and ``items`` (list of item
                dicts), plus optional ``version`` and ``description``.

        Returns:
            A new EvaluationDataset instance.

        """
        raw_items = data.get("items")
        if not isinstance(raw_items, Sequence):
            msg = "Dataset requires an 'items' list"
            raise ValueError(msg)
        items = tuple(DatasetItem.from_dict(item) for item in raw_items)
        return cls(
            name=str(data.get("name") or "dataset"),
            items=items,
            version=str(data.get("version") or "1.0.0"),
            description=_optional_str(data.get("description")),
        )


def _optional_str(value: object) -> str | None:
    """Return a string value or None for missing/empty values.

    Args:
        value: The raw value.

    Returns:
        The string representation, or None.

    """
    if value is None:
        return None
    text = str(value)
    return text if text else None
