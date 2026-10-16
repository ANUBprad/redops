"""Regression tests for the metric-validation CLI's ground-truth gate."""

from __future__ import annotations

import asyncio
import runpy
import sys
from pathlib import Path

from app.evaluation.validation.loader import ValidationDatasetLoader


def test_repository_fixture_is_explicitly_not_ground_truth() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    dataset = asyncio.run(
        ValidationDatasetLoader().load(str(repo_root / "scripts/validation_data/ground_truth"))
    )
    assert dataset.provenance.is_ground_truth is False


def test_cli_refuses_to_report_accuracy_for_synthetic_fixture(
    monkeypatch, capsys
) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "validate_metrics.py"
    corpus = repo_root / "scripts" / "validation_data" / "ground_truth"
    monkeypatch.setattr(sys, "argv", [str(script), "--corpus", str(corpus)])
    namespace = runpy.run_path(str(script), run_name="redops_validation_cli_test")

    assert namespace["main"]() == 2
    captured = capsys.readouterr()
    assert "not marked as genuine ground truth" in captured.err
    assert "Overall Accuracy" not in captured.out
