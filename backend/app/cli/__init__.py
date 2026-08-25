"""Evaluation regression CLI.

Minimal developer-facing tool for comparing evaluation runs
and detecting regressions. Designed for CI integration.

Usage:
    python -m app.cli compare --baseline <run-id> --current <run-id>
    python -m app.cli compare --baseline <run-id> --current <run-id> --json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="redops",
        description="RedOps evaluation regression CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare two evaluation runs for regression",
    )
    compare_parser.add_argument(
        "--baseline",
        required=True,
        help="Baseline evaluation run ID",
    )
    compare_parser.add_argument(
        "--current",
        required=True,
        help="Current evaluation run ID",
    )
    compare_parser.add_argument(
        "--tolerance",
        type=float,
        default=0.02,
        help="Regression tolerance (default: 0.02)",
    )
    compare_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output result as JSON",
    )

    return parser


def _format_comparison_report(result: Any) -> str:
    """Format a RegressionResult as human-readable text."""
    lines: list[str] = []

    lines.append("=" * 60)
    lines.append("EVALUATION REGRESSION REPORT")
    lines.append("=" * 60)
    lines.append(f"Baseline:    {result.baseline_run_id}")
    lines.append(f"Current:     {result.current_run_id}")
    lines.append(f"Verdict:     {result.verdict.value.upper()}")
    lines.append("")

    # Fingerprint status
    fp_status = "COMPATIBLE" if result.fingerprints_compatible else "INCOMPATIBLE"
    lines.append(f"Fingerprints: {fp_status}")
    if not result.fingerprints_compatible:
        lines.append(f"  Baseline: {result.baseline_fingerprint}")
        lines.append(f"  Current:  {result.current_fingerprint}")
    lines.append("")

    # Per-metric results
    lines.append("METRIC RESULTS:")
    lines.append("-" * 60)
    for mc in result.metric_comparisons:
        status_icon = {
            "pass": "PASS",
            "regression": "FAIL",
            "improvement": "PASS",
            "no_change": "PASS",
            "not_comparable": "N/A",
            "added": "NEW",
            "removed": "GONE",
            "error": "ERR",
        }.get(mc.status.value, "??")

        b_str = f"{mc.baseline_score:.4f}" if mc.baseline_score is not None else "N/A"
        c_str = f"{mc.current_score:.4f}" if mc.current_score is not None else "N/A"
        delta_str = (
            f"{mc.delta:+.4f}"
            if mc.baseline_score is not None and mc.current_score is not None
            else "N/A"
        )

        lines.append(
            f"  [{status_icon:>4}] {mc.metric_name:<30} "
            f"baseline={b_str:>10}  current={c_str:>10}  delta={delta_str:>10}"
        )
        if mc.reasoning:
            lines.append(f"         {mc.reasoning}")
    lines.append("")

    # Summary
    lines.append("SUMMARY:")
    lines.append(f"  Metrics compared:  {len(result.metric_comparisons)}")
    lines.append(f"  Regressions:       {result.regression_count}")
    lines.append(f"  Errors:            {result.error_count}")
    lines.append(f"  Not comparable:    {result.not_comparable_count}")
    lines.append("")
    lines.append(f"Reasoning: {result.reasoning}")
    lines.append("=" * 60)

    return "\n".join(lines)


def _result_to_dict(result: Any) -> dict[str, Any]:
    """Convert a RegressionResult to a JSON-serializable dict."""
    return {
        "baseline_run_id": result.baseline_run_id,
        "current_run_id": result.current_run_id,
        "baseline_fingerprint": result.baseline_fingerprint,
        "current_fingerprint": result.current_fingerprint,
        "fingerprints_compatible": result.fingerprints_compatible,
        "verdict": result.verdict.value,
        "regression_count": result.regression_count,
        "error_count": result.error_count,
        "not_comparable_count": result.not_comparable_count,
        "reasoning": result.reasoning,
        "metric_comparisons": [
            {
                "metric_name": mc.metric_name,
                "baseline_score": mc.baseline_score,
                "current_score": mc.current_score,
                "delta": mc.delta,
                "direction": mc.direction.value,
                "tolerance": mc.tolerance,
                "status": mc.status.value,
                "reasoning": mc.reasoning,
            }
            for mc in result.metric_comparisons
        ],
    }


async def _run_compare(args: argparse.Namespace) -> int:
    """Execute the compare command. Returns exit code."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.core.config import get_config
    from app.evaluation.regression import RegressionConfig, analyze_regression
    from app.evaluation.reliability.fingerprint import compute_fingerprint
    from app.evaluation.replay.composite_repository import CompositeTraceRepository
    from app.evaluation.replay.database_repository import DatabaseTraceRepository
    from app.evaluation.replay.service import ReplayService

    app_config = get_config()
    engine = create_async_engine(app_config.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        db_repo = DatabaseTraceRepository(session)
        service = ReplayService(db_repo)

        baseline_trace = await service.load_trace(args.baseline)
        if baseline_trace is None:
            print(f"ERROR: Baseline trace not found for run {args.baseline}", file=sys.stderr)
            return 4

        current_trace = await service.load_trace(args.current)
        if current_trace is None:
            print(f"ERROR: Current trace not found for run {args.current}", file=sys.stderr)
            return 4

    # Extract metrics from traces
    baseline_scores: dict[str, list[float]] = {}
    for item in baseline_trace.item_traces:
        for mt in item.metric_traces:
            if mt.metric_name not in baseline_scores:
                baseline_scores[mt.metric_name] = []
            baseline_scores[mt.metric_name].append(mt.normalized_score)

    current_scores: dict[str, list[float]] = {}
    for item in current_trace.item_traces:
        for mt in item.metric_traces:
            if mt.metric_name not in current_scores:
                current_scores[mt.metric_name] = []
            current_scores[mt.metric_name].append(mt.normalized_score)

    # Average scores per metric
    baseline_avg = {
        name: sum(scores) / len(scores) if scores else None
        for name, scores in baseline_scores.items()
    }
    current_avg = {
        name: sum(scores) / len(scores) if scores else None
        for name, scores in current_scores.items()
    }

    baseline_fingerprint = compute_fingerprint(**baseline_trace.configuration)
    current_fingerprint = compute_fingerprint(**current_trace.configuration)

    # Run regression analysis
    config = RegressionConfig(default_tolerance=args.tolerance)
    result = analyze_regression(
        baseline_run_id=args.baseline,
        current_run_id=args.current,
        baseline_fingerprint=baseline_fingerprint.fingerprint,
        current_fingerprint=current_fingerprint.fingerprint,
        baseline_metrics=baseline_avg,
        current_metrics=current_avg,
        config=config,
    )

    # Output
    if args.json_output:
        print(json.dumps(_result_to_dict(result), indent=2))
    else:
        print(_format_comparison_report(result))

    # Exit code: 0 = pass, 1 = regression, 2 = error, 3 = not comparable, 4 = not found
    if result.verdict.value == "pass":
        return 0
    elif result.verdict.value == "fail":
        return 1
    elif result.verdict.value == "error":
        return 2
    elif result.verdict.value == "not_comparable":
        return 3
    return 1


def main() -> None:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "compare":
        import asyncio

        exit_code = asyncio.run(_run_compare(args))
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
