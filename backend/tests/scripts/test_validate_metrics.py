"""Tests for the validation CLI entry point."""

from __future__ import annotations

import json
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

    def test_test_split_passes_with_low_threshold(self) -> None:
        code, out, _err = run_cli(["--split", "test", "--threshold", "0.5"])
        assert code == 0
        assert "PASS" in out
        assert "100.00%" in out

    def test_test_split_passes_with_high_threshold(self) -> None:
        code, out, _err = run_cli(["--split", "test", "--threshold", "0.9"])
        assert code == 0
        assert "PASS" in out

    def test_all_split_fails_high_threshold(self) -> None:
        code, out, _err = run_cli(["--split", "all", "--threshold", "0.9"])
        assert code == 1
        assert "FAIL" in out

    def test_output_json_is_valid(self, tmp_path: Path) -> None:
        output_file = tmp_path / "report.json"
        code, _out, _err = run_cli(["--split", "test", "--output", str(output_file)])
        assert code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "summary" in data
        assert "confusion_matrix" in data
        assert "manifest" in data
        assert data["summary"]["example_count"] == 18
        assert data["summary"]["accuracy"] == 1.0

    def test_verbose_output_includes_examples(self) -> None:
        code, out, _err = run_cli(["--split", "test", "--verbose"])
        assert code == 0
        assert "Per-Example Outcomes" in out
        assert "gt-harm-unsafe-1" in out


class TestMutationDetection:
    """Mutation-style tests: deliberately corrupt ground truth and verify detection."""

    def test_flipped_ground_truth_detected(self, tmp_path: Path) -> None:
        """Flip safe/unsafe labels and verify validation fails."""
        import asyncio

        from app.evaluation.validation.loader import ValidationDatasetLoader
        from app.evaluation.validation.model import ValidationDataset
        from app.evaluation.validation.runner import run_validation

        # Load original dataset
        loader = ValidationDatasetLoader()
        dataset = asyncio.run(loader.load(str(CORPUS_DIR)))

        # Create mutated dataset with flipped labels
        mutated_examples = []
        for ex in dataset.examples:
            flipped_label = "unsafe" if ex.ground_truth.value == "safe" else "safe"
            ex_dict = ex.to_dict()
            ex_dict["ground_truth"] = flipped_label
            mutated_examples.append(ex_dict)

        mutated_dataset = ValidationDataset.from_dict(
            {
                "provenance": dataset.provenance.to_dict(),
                "examples": mutated_examples,
            }
        )

        # Run validation on mutated dataset
        result = run_validation(mutated_dataset)

        # With flipped labels, accuracy should be very low
        # Original: 18 unsafe, 18 safe
        # Flipped: metric predicts unsafe for all 18 originally unsafe (now labeled safe) = 18 FP
        #           metric predicts safe for some originally safe (now labeled unsafe) = some FN
        total = result.overall.total
        correct = result.overall.true_positives + result.overall.true_negatives
        accuracy = correct / total if total > 0 else 0

        # Accuracy should be much lower than original
        assert accuracy < 0.5, f"Mutated dataset accuracy {accuracy:.2%} should be < 50%"

    def test_metric_mutation_detected(self, tmp_path: Path) -> None:
        """Use a deliberately wrong scorer and verify validation fails."""
        import asyncio

        from app.evaluation.validation.loader import ValidationDatasetLoader
        from app.evaluation.validation.runner import run_validation

        loader = ValidationDatasetLoader()
        dataset = asyncio.run(loader.load(str(CORPUS_DIR)))

        # Use a scorer that always predicts unsafe (True)
        def wrong_scorer(*, prompt: str, response: str) -> bool:
            return True

        _result = run_validation(dataset, scorer=wrong_scorer, splits=["test"])

        # Test split has 18 unsafe examples, all predicted unsafe = 18 TP
        # But if we use train split (12 safe), all predicted unsafe = 12 FP
        result_train = run_validation(dataset, scorer=wrong_scorer, splits=["train"])
        assert result_train.overall.false_positives == 12
        assert result_train.overall.true_negatives == 0

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
