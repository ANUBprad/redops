#!/usr/bin/env python
"""Ground-truth validation CLI for RedOps safety metrics.

This script loads a ground-truth validation corpus and runs the
keyword safety metric against it, producing a validation report.

Usage:
    python -m scripts.validate_metrics [--corpus PATH] [--split SPLIT] [--threshold FLOAT]

Exit codes:
    0 - Validation passed (all metrics meet threshold)
    1 - Validation failed (metrics below threshold or errors)
    2 - Usage/error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.evaluation.validation.loader import (
    ValidationDatasetLoader,
    ValidationDatasetLoadError,
)
from app.evaluation.validation.reproducibility import build_run_manifest
from app.evaluation.validation.runner import run_validation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run ground-truth validation for RedOps safety metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("scripts/validation_data/ground_truth"),
        help="Path to validation corpus directory (default: scripts/validation_data/ground_truth)",
    )
    parser.add_argument(
        "--split",
        choices=["train", "dev", "test", "all"],
        default="test",
        help="Dataset split to evaluate (default: test)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="Minimum accuracy threshold for pass (default: 0.8)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write validation report to JSON file",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-example outcomes",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Load dataset
    try:
        loader = ValidationDatasetLoader()
        import asyncio

        dataset = asyncio.run(loader.load(str(args.corpus)))
    except ValidationDatasetLoadError as e:
        print(f"ERROR: Failed to load validation corpus: {e}", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print(f"ERROR: Corpus directory not found: {args.corpus}", file=sys.stderr)
        return 2

    # Determine splits to evaluate
    splits = None if args.split == "all" else [args.split]

    # Run validation
    try:
        result = run_validation(dataset, splits=splits)
    except Exception as e:
        print(f"ERROR: Validation failed: {e}", file=sys.stderr)
        return 1

    # Compute accuracy
    total = result.overall.total
    if total == 0:
        print("WARNING: No examples evaluated", file=sys.stderr)
        return 1

    correct = result.overall.true_positives + result.overall.true_negatives
    accuracy = correct / total

    # Print summary
    print("=" * 60)
    print("RedOps Ground-Truth Validation Report")
    print("=" * 60)
    print(f"Corpus: {dataset.provenance.name} v{dataset.provenance.version}")
    print(f"Ground truth: {dataset.provenance.is_ground_truth}")
    print(f"Split(s): {args.split}")
    print(f"Metric: {result.metric_configuration.name} v{result.metric_configuration.version}")
    print(f"Examples: {result.example_count}")
    print("-" * 60)
    print(f"Overall Accuracy: {accuracy:.2%} ({correct}/{total})")
    print(f"  True Positives:  {result.overall.true_positives}")
    print(f"  True Negatives:  {result.overall.true_negatives}")
    print(f"  False Positives: {result.overall.false_positives}")
    print(f"  False Negatives: {result.overall.false_negatives}")
    print("-" * 60)

    # Per-category breakdown
    print("Per-Category Breakdown:")
    for cat, counts in sorted(result.category_counts.items()):
        cat_total = counts.total
        if cat_total > 0:
            cat_correct = counts.true_positives + counts.true_negatives
            cat_acc = cat_correct / cat_total
            print(
                f"  {cat}: {cat_acc:.2%} ({cat_correct}/{cat_total}) "
                f"[TP={counts.true_positives}, TN={counts.true_negatives}, "
                f"FP={counts.false_positives}, FN={counts.false_negatives}]"
            )

    print("-" * 60)

    # Verbose per-example output
    if args.verbose:
        print("\nPer-Example Outcomes:")
        for outcome in result.outcomes:
            status = "PASS" if (outcome.is_true_positive or outcome.is_true_negative) else "FAIL"
            print(
                f"  [{status}] {outcome.example_id} ({outcome.category}): "
                f"ground_truth={outcome.ground_truth.value}, "
                f"predicted={outcome.predicted_label.value}, "
                f"verdict={outcome.overall_verdict}"
            )

    # Check threshold
    passed = accuracy >= args.threshold
    print("-" * 60)
    if passed:
        print(f"RESULT: PASS (accuracy {accuracy:.2%} >= threshold {args.threshold:.2%})")
    else:
        print(f"RESULT: FAIL (accuracy {accuracy:.2%} < threshold {args.threshold:.2%})")

    # Write JSON output if requested
    if args.output:
        try:
            manifest = build_run_manifest(dataset, result)
            output_data = {
                "summary": {
                    "corpus": dataset.provenance.name,
                    "corpus_version": dataset.provenance.version,
                    "is_ground_truth": dataset.provenance.is_ground_truth,
                    "split": args.split,
                    "metric": result.metric_configuration.as_dict(),
                    "example_count": result.example_count,
                    "accuracy": accuracy,
                    "threshold": args.threshold,
                    "passed": passed,
                },
                "confusion_matrix": {
                    "overall": result.overall.as_dict(),
                    "by_category": {
                        cat: counts.as_dict() for cat, counts in result.category_counts.items()
                    },
                },
                "manifest": manifest.to_dict(),
            }
            if args.verbose:
                output_data["outcomes"] = [o.as_dict() for o in result.outcomes]

            args.output.write_text(json.dumps(output_data, indent=2))
            print(f"\nReport written to: {args.output}")
        except Exception as e:
            print(f"WARNING: Failed to write output file: {e}", file=sys.stderr)

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
