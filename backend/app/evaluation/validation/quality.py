"""Deterministic quality checks and statistics for a validation corpus.

These checks quantify the composition of a ``ValidationDataset`` (counts,
label/category/split distributions, missing metadata, duplicate ids) without
imposing any arbitrary balance target. Imbalance is *reported*, never silently
corrected, because rebalancing or relabeling to hit a number would invalidate
the ground-truth semantics of the corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.evaluation.validation.enums import GroundTruthSafetyLabel, ValidationSplit

if TYPE_CHECKING:
    from app.evaluation.validation.model import ValidationDataset, ValidationExample


@dataclass(frozen=True, slots=True)
class DatasetStatistics:
    """Compositional statistics for a validation corpus."""

    total_examples: int = 0
    safe_count: int = 0
    unsafe_count: int = 0
    label_distribution: dict[str, int] = field(default_factory=dict)
    category_distribution: dict[str, int] = field(default_factory=dict)
    split_distribution: dict[str, int] = field(default_factory=dict)
    missing_metadata_count: int = 0
    duplicate_id_count: int = 0
    empty_response_count: int = 0

    def as_dict(self) -> dict[str, object]:
        """Return the statistics as a plain JSON-serializable dict."""
        return {
            "total_examples": self.total_examples,
            "safe_count": self.safe_count,
            "unsafe_count": self.unsafe_count,
            "label_distribution": dict(self.label_distribution),
            "category_distribution": dict(self.category_distribution),
            "split_distribution": dict(self.split_distribution),
            "missing_metadata_count": self.missing_metadata_count,
            "duplicate_id_count": self.duplicate_id_count,
            "empty_response_count": self.empty_response_count,
        }


def compute_statistics(dataset: ValidationDataset) -> DatasetStatistics:
    """Compute compositional statistics for a validation corpus.

    The dataset is expected to be already validated (unique ids enforced on
    construction), so ``duplicate_id_count`` is computed defensively but will
    normally be zero.

    Args:
        dataset: The validated corpus.

    Returns:
        ``DatasetStatistics`` describing the corpus composition.
    """
    safe = 0
    unsafe = 0
    label_dist: dict[str, int] = {}
    category_dist: dict[str, int] = {}
    split_dist: dict[str, int] = {}
    missing_metadata = 0
    empty_responses = 0

    for example in dataset.examples:
        if example.ground_truth is GroundTruthSafetyLabel.SAFE:
            safe += 1
        else:
            unsafe += 1
        label_dist[example.ground_truth.value] = label_dist.get(example.ground_truth.value, 0) + 1
        category_dist[example.category] = category_dist.get(example.category, 0) + 1
        split_dist[example.split.value] = split_dist.get(example.split.value, 0) + 1

        if not example.prompt.strip() or not example.response.strip():
            missing_metadata += 1
        if not example.response.strip():
            empty_responses += 1

    duplicate_count = _count_duplicate_ids(dataset.examples)

    return DatasetStatistics(
        total_examples=len(dataset.examples),
        safe_count=safe,
        unsafe_count=unsafe,
        label_distribution=label_dist,
        category_distribution=category_dist,
        split_distribution=split_dist,
        missing_metadata_count=missing_metadata,
        duplicate_id_count=duplicate_count,
        empty_response_count=empty_responses,
    )


def _count_duplicate_ids(examples: tuple[ValidationExample, ...]) -> int:
    """Defensively count duplicate ids beyond the first occurrence each."""
    counts: dict[str, int] = {}
    for example in examples:
        counts[example.id] = counts.get(example.id, 0) + 1
    return sum(v - 1 for v in counts.values() if v > 1)


def validate_split_has_test(dataset: ValidationDataset) -> bool:
    """Return whether the corpus contains at least one TEST split example.

    A corpus without a held-out TEST split cannot support a defensible claim
    that a metric generalizes beyond the data it was tuned/validated on.
    """
    return any(e.split is ValidationSplit.TEST for e in dataset.examples)
