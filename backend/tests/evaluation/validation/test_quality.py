"""Tests for corpus quality statistics and checks."""

from __future__ import annotations

from app.evaluation.validation.model import ValidationDataset
from app.evaluation.validation.quality import (
    compute_statistics,
    validate_split_has_test,
)


def _example(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "ex-1",
        "prompt": "p",
        "response": "r",
        "ground_truth": "safe",
        "category": "harmlessness",
        "split": "test",
    }
    base.update(overrides)
    return base


def _dataset(examples: list[dict[str, object]]) -> ValidationDataset:
    return ValidationDataset.from_dict(
        {"provenance": {"name": "c", "version": "1.0.0"}, "examples": examples}
    )


class TestComputeStatistics:
    def test_counts_and_distributions(self) -> None:
        dataset = _dataset(
            [
                _example(id="a", split="test", category="harmlessness"),
                _example(
                    id="b",
                    split="dev",
                    category="data_confidentiality",
                    ground_truth="unsafe",
                ),
                _example(id="c", split="test", category="harmlessness"),
            ]
        )
        stats = compute_statistics(dataset)
        assert stats.total_examples == 3
        assert stats.safe_count == 2
        assert stats.unsafe_count == 1
        assert stats.label_distribution == {"safe": 2, "unsafe": 1}
        assert stats.category_distribution == {"harmlessness": 2, "data_confidentiality": 1}
        assert stats.split_distribution == {"test": 2, "dev": 1}
        assert stats.duplicate_id_count == 0

    def test_empty_response_counted(self) -> None:
        dataset = _dataset([_example(id="a", response="   ")])
        stats = compute_statistics(dataset)
        assert stats.missing_metadata_count == 1
        assert stats.empty_response_count == 1

    def test_empty_dataset(self) -> None:
        stats = compute_statistics(_dataset([]))
        assert stats.total_examples == 0
        assert stats.safe_count == 0
        assert stats.unsafe_count == 0

    def test_as_dict_serializable(self) -> None:
        stats = compute_statistics(_dataset([_example(id="a")]))
        assert isinstance(stats.as_dict(), dict)


class TestValidateSplitHasTest:
    def test_true_when_test_present(self) -> None:
        dataset = _dataset([_example(id="a", split="test")])
        assert validate_split_has_test(dataset) is True

    def test_false_without_test(self) -> None:
        dataset = _dataset([_example(id="a", split="train"), _example(id="b", split="dev")])
        assert validate_split_has_test(dataset) is False

    def test_false_for_empty(self) -> None:
        assert validate_split_has_test(_dataset([])) is False
