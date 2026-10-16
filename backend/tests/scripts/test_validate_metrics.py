"""Tests for the validation CLI entry point."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = REPO_ROOT / "scripts" / "validation_data" / "ground_truth"


def run_cli(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run the validation CLI and return (exit_code, stdout, stderr)."""
    if cwd is None:
        cwd = REPO_ROOT
    env = {**__import__("os").environ, "PYTHONPATH": str(cwd / "backend")}
    result = subprocess.run(  # noqa: S603 - known script path, no untrusted input
        [sys.executable, "scripts/validate_metrics.py", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


class TestValidationCLI:
    """Tests for the validate_metrics.py CLI."""

    def test_help_exits_zero(self) -> None:
        code, out, _err = run_cli(["--help"])
        assert code == 0
        assert "usage:" in out.lower()
        assert "validate_metrics" in out

    def test_invalid_corpus_exits_two(self) -> None:
        code, out, err = run_cli(["--corpus", "nonexistent"])
        assert code == 2
        assert "ERROR" in err or "ERROR" in out

    def test_synthetic_test_split_is_rejected_even_with_low_threshold(self) -> None:
        code, out, err = run_cli(["--split", "test", "--threshold", "0.5"])
        assert code == 2
        assert "not marked as genuine ground truth" in err
        assert "Overall Accuracy" not in out

    def test_synthetic_test_split_is_rejected_with_high_threshold(self) -> None:
        code, out, err = run_cli(["--split", "test", "--threshold", "0.9"])
        assert code == 2
        assert "not marked as genuine ground truth" in err
        assert "Overall Accuracy" not in out

    def test_all_synthetic_splits_are_rejected(self) -> None:
        code, out, err = run_cli(["--split", "all", "--threshold", "0.9"])
        assert code == 2
        assert "not marked as genuine ground truth" in err
        assert "Overall Accuracy" not in out

    def test_output_json_is_not_written_for_synthetic_corpus(self, tmp_path: Path) -> None:
        output_file = tmp_path / "report.json"
        code, out, err = run_cli(["--split", "test", "--output", str(output_file)])
        assert code == 2
        assert "not marked as genuine ground truth" in err
        assert "Overall Accuracy" not in out
        assert not output_file.exists()

    def test_verbose_mode_does_not_bypass_synthetic_corpus_guard(self) -> None:
        code, out, err = run_cli(["--split", "test", "--verbose"])
        assert code == 2
        assert "not marked as genuine ground truth" in err
        assert "Per-Example Outcomes" not in out


class TestMutationDetection:
    """Synthetic unit fixtures verify confusion-matrix mechanics, not metric accuracy."""

    def test_flipped_labels_flip_confusion_outcomes(self, tmp_path: Path) -> None:
        from app.evaluation.validation.model import ValidationDataset
        from app.evaluation.validation.runner import run_validation

        dataset = ValidationDataset.from_dict(
            {
                "provenance": {
                    "name": "synthetic-runner-math-fixture",
                    "is_ground_truth": False,
                    "note": "Unit fixture for confusion-matrix mechanics only.",
                },
                "examples": [
                    {
                        "id": "complied",
                        "prompt": "test prompt",
                        "response": "complied",
                        "ground_truth": "unsafe",
                        "split": "test",
                    },
                    {
                        "id": "refused",
                        "prompt": "test prompt",
                        "response": "refused",
                        "ground_truth": "safe",
                        "split": "test",
                    },
                ],
            }
        )

        def scorer(*, prompt: str, response: str) -> bool:
            return response == "complied"

        original = run_validation(dataset, scorer=scorer)
        flipped_examples = []
        for example in dataset.examples:
            item = example.to_dict()
            item["ground_truth"] = "safe" if example.is_unsafe else "unsafe"
            flipped_examples.append(item)
        mutated = ValidationDataset.from_dict(
            {
                "provenance": dataset.provenance.to_dict(),
                "examples": flipped_examples,
            }
        )
        flipped = run_validation(mutated, scorer=scorer)

        assert original.overall.true_positives == 1
        assert original.overall.true_negatives == 1
        assert flipped.overall.false_positives == 1
        assert flipped.overall.false_negatives == 1

    def test_wrong_scorer_produces_expected_confusion_counts(self, tmp_path: Path) -> None:
        from app.evaluation.validation.model import ValidationDataset
        from app.evaluation.validation.runner import run_validation

        dataset = ValidationDataset.from_dict(
            {
                "provenance": {
                    "name": "synthetic-runner-math-fixture",
                    "is_ground_truth": False,
                    "note": "Unit fixture for confusion-matrix mechanics only.",
                },
                "examples": [
                    {
                        "id": "unsafe",
                        "prompt": "test prompt",
                        "response": "unsafe response",
                        "ground_truth": "unsafe",
                        "split": "train",
                    },
                    {
                        "id": "safe",
                        "prompt": "test prompt",
                        "response": "safe response",
                        "ground_truth": "safe",
                        "split": "train",
                    },
                ],
            }
        )

        def always_unsafe(*, prompt: str, response: str) -> bool:
            return True

        result = run_validation(dataset, scorer=always_unsafe, splits=["train"])
        assert result.overall.true_positives == 1
        assert result.overall.false_positives == 1
        assert result.overall.false_negatives == 0
        assert result.overall.true_negatives == 0

    def test_corrupted_example_detected(self, tmp_path: Path) -> None:
        """Add a malformed example and verify loader rejects it."""
        import asyncio
        import tempfile

        from app.evaluation.validation.loader import (
            ValidationDatasetLoader,
            ValidationDatasetLoadError,
        )

        # Create a corrupted corpus
        with tempfile.TemporaryDirectory() as tmpdir:
            corpus_dir = Path(tmpdir)
            (corpus_dir / "provenance.json").write_text(
                '{"name": "test", "version": "1.0.0", "is_ground_truth": true}'
            )
            # Write valid example
            (corpus_dir / "examples.jsonl").write_text(
                '{"id": "ex1", "prompt": "test", "response": "I cannot help", "ground_truth": "safe", "category": "harmlessness", "split": "test", "annotation_confidence": "high"}\n'
                '{"id": "ex2", "prompt": "test2", "response": "bad", "ground_truth": "maybe", "category": "harmlessness", "split": "test", "annotation_confidence": "high"}\n'
            )

            loader = ValidationDatasetLoader()
            try:
                asyncio.run(loader.load(str(corpus_dir)))
                assert False, "Should have raised ValidationDatasetLoadError"
            except ValidationDatasetLoadError as e:
                assert "invalid ground_truth" in str(e).lower() or "maybe" in str(e).lower()
