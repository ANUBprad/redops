#!/usr/bin/env python3
"""redops-gate — Evaluation Gate CLI.

Triggers an evaluation run against the RedOps Eval API and blocks (exits
non-zero) when any configured metric threshold is breached. Designed for
use in CI/CD pipelines as a quality gate.

The client uses only the Python standard library so it can run in any
environment (CI runners, containers, developer machines) without extra
dependencies.

Exit codes:
    0   Gate passed (all metrics within thresholds).
    1   At least one metric breached a threshold.
    2   Usage / configuration error.
    3   Evaluation run failed or was cancelled.
    4   Timed out waiting for the run to complete.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_POLL_INTERVAL = 5.0
DEFAULT_TIMEOUT = 1800.0

# Run statuses considered "terminal" for the gate.
COMPLETED_STATUS = "completed"
FAILED_STATUS = "failed"
CANCELLED_STATUS = "cancelled"

TERMINAL_STATUSES = frozenset(
    {COMPLETED_STATUS, FAILED_STATUS, CANCELLED_STATUS,
     "completed_with_errors"}
)


def _build_headers(api_key: str | None, idempotency_key: str | None) -> dict[str, str]:
    """Build request headers with optional auth and idempotency key."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _request(
    url: str,
    headers: dict[str, str],
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Perform an HTTP request and return the parsed JSON response."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            if not body:
                return {}
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = _extract_error_detail(exc)
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach {url}: {exc.reason}") from exc


def _extract_error_detail(exc: urllib.error.HTTPError) -> str:
    """Best-effort extraction of a FastAPI error detail message."""
    try:
        body = json.loads(exc.read().decode("utf-8"))
        return body.get("detail", exc.reason)
    except Exception:
        return str(exc.reason)


def _trigger_run(
    api_url: str,
    headers: dict[str, str],
    evaluation_id: str,
    provider: str,
    model: str,
    metrics: list[str],
) -> dict[str, Any]:
    """Create a new evaluation run and return the run response."""
    url = f"{api_url}/api/v1/runs"
    payload: dict[str, Any] = {
        "evaluation_id": evaluation_id,
        "provider": provider,
        "model": model,
        "metrics": metrics,
        "dataset_items": [],
    }
    return _request(url, headers, method="POST", payload=payload)


def _get_run(
    api_url: str,
    headers: dict[str, str],
    run_id: str,
) -> dict[str, Any]:
    """Fetch the current state of an evaluation run."""
    url = f"{api_url}/api/v1/runs/{run_id}"
    return _request(url, headers)


def _collect_metrics(
    api_url: str, headers: dict[str, str], run_id: str
) -> dict[str, float]:
    """Fetch aggregated metric scores for a completed run."""
    url = f"{api_url}/api/v1/runs/{run_id}/metrics"
    try:
        payload = _request(url, headers)
    except RuntimeError:
        # Metrics endpoint may be unavailable; fall back to empty map.
        return {}
    results = payload.get("results") or payload.get("metrics") or []
    scores: dict[str, float] = {}
    if isinstance(results, list):
        for entry in results:
            name = entry.get("metric") or entry.get("name")
            value = entry.get("score") or entry.get("value")
            if name is not None and value is not None:
                try:
                    scores[str(name)] = float(value)
                except (TypeError, ValueError):
                    continue
    elif isinstance(results, dict):
        for name, value in results.items():
            try:
                scores[str(name)] = float(value)
            except (TypeError, ValueError):
                continue
    return scores


def _parse_thresholds(specs: list[str]) -> list[tuple[str, float, str]]:
    """Parse threshold specs like 'accuracy>=0.9' into (metric, value, op)."""
    parsed: list[tuple[str, float, str]] = []
    for spec in specs:
        operator = None
        for candidate in (">=", "<=", ">", "<", "==", "!="):
            if candidate in spec:
                operator = candidate
                break
        if operator is None:
            raise argparse.ArgumentTypeError(
                f"invalid threshold '{spec}': expected '<metric><op><value>' "
                f"with op in >=, <=, >, <, ==, !="
            )
        metric, _, value_str = spec.partition(operator)
        try:
            value = float(value_str)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"invalid threshold value '{value_str}' in '{spec}'"
            ) from exc
        parsed.append((metric.strip(), value, operator))
    return parsed


def _check_thresholds(
    scores: dict[str, float], thresholds: list[tuple[str, float, str]]
) -> tuple[bool, list[str]]:
    """Compare collected scores against thresholds.

    Returns (passed, violations) where violations lists human-readable
    descriptions of the metrics that breached their thresholds.
    """
    violations: list[str] = []
    for metric, expected, op in thresholds:
        actual = scores.get(metric)
        if actual is None:
            violations.append(f"metric '{metric}' has no score")
            continue
        ok = {
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
        }[op](actual, expected)
        if not ok:
            violations.append(
                f"metric '{metric}' = {actual:.4f} failed {op} {expected}"
            )
    return len(violations) == 0, violations


def _resolve_evaluation_id(
    api_url: str,
    headers: dict[str, str],
    evaluation_id: str | None,
    evaluation_name: str | None,
) -> str:
    """Resolve an evaluation by ID or by name via the list endpoint."""
    if evaluation_id:
        return evaluation_id
    if not evaluation_name:
        raise RuntimeError(
            "either --evaluation-id or --evaluation-name is required"
        )
    url = f"{api_url}/api/v1/evaluations"
    payload = _request(url, headers)
    items = payload.get("items") or payload.get("results") or []
    for item in items:
        if item.get("name") == evaluation_name:
            return str(item["id"])
    raise RuntimeError(f"no evaluation found with name '{evaluation_name}'")


def run_gate(args: argparse.Namespace) -> int:
    """Execute the evaluation gate and return a process exit code."""
    headers = _build_headers(args.api_key, args.idempotency_key)

    try:
        evaluation_id = _resolve_evaluation_id(
            args.api_url, headers, args.evaluation_id, args.evaluation_name
        )
        run = _trigger_run(
            api_url=args.api_url,
            headers=headers,
            evaluation_id=evaluation_id,
            provider=args.provider,
            model=args.model,
            metrics=args.metrics,
        )
    except RuntimeError as exc:
        print(f"redops-gate: error triggering run: {exc}", file=sys.stderr)
        return 2

    run_id = str(run["id"])
    print(f"redops-gate: started run {run_id} (idempotency: {args.idempotency_key or 'none'})")

    deadline = time.monotonic() + args.timeout
    run_payload = run
    while True:
        status = run_payload.get("status")
        print(
            f"redops-gate: run status '{status}' "
            f"({run_payload.get('items_completed', 0)}/"
            f"{run_payload.get('items_total', 0)})"
        )
        if status in TERMINAL_STATUSES:
            break
        if time.monotonic() >= deadline:
            print(
                f"redops-gate: timed out after {args.timeout:.1f}s waiting for "
                f"run {run_id}",
                file=sys.stderr,
            )
            return 4
        time.sleep(args.poll_interval)
        run_payload = _get_run(args.api_url, headers, run_id)

    if status in (FAILED_STATUS, CANCELLED_STATUS):
        reason = run_payload.get("failure_reason") or "see API"
        print(f"redops-gate: run {run_id} ended with status '{status}': {reason}",
              file=sys.stderr)
        return 3

    scores = _collect_metrics(args.api_url, headers, run_id)
    print(
        f"redops-gate: run {run_id} completed, {len(scores)} metric(s) collected"
    )

    passed, violations = _check_thresholds(scores, args.thresholds)
    if passed:
        print("redops-gate: all thresholds satisfied — gate PASSED")
        return 0

    print("redops-gate: gate FAILED — threshold breach(es):", file=sys.stderr)
    for violation in violations:
        print(f"  - {violation}", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    """Construct the redops-gate argument parser."""
    parser = argparse.ArgumentParser(
        prog="redops-gate",
        description=(
            "Trigger an evaluation run and block on threshold breach for "
            "use as a CI/CD quality gate."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="trigger an evaluation and block on threshold breach"
    )
    run_parser.add_argument(
        "--api-url",
        default=os.environ.get("REDOPS_API_URL", DEFAULT_API_URL),
        help="base URL of the RedOps Eval API",
    )
    run_parser.add_argument(
        "--api-key",
        default=os.environ.get("REDOPS_API_KEY"),
        help="API key or JWT for authentication",
    )
    run_parser.add_argument(
        "--evaluation-id",
        help="ID of the evaluation to run",
    )
    run_parser.add_argument(
        "--evaluation-name",
        help="name of the evaluation to run (resolved via the API)",
    )
    run_parser.add_argument(
        "--provider",
        required=True,
        help="provider name (e.g. openai, anthropic)",
    )
    run_parser.add_argument(
        "--model",
        required=True,
        help="model id to evaluate",
    )
    run_parser.add_argument(
        "--metric",
        dest="metrics",
        action="append",
        default=[],
        help="metric name to include in the run (repeatable)",
    )
    run_parser.add_argument(
        "--threshold",
        dest="thresholds",
        action="append",
        default=[],
        type=_parse_thresholds,
        help="gate threshold '<metric><op><value>' (repeatable), e.g. "
        "--threshold 'accuracy>=0.9'",
    )
    run_parser.add_argument(
        "--idempotency-key",
        default=os.environ.get("REDOPS_IDEMPOTENCY_KEY"),
        help="idempotency key enabling safe CI/CD retries",
    )
    run_parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="maximum seconds to wait for the run (default: 1800)",
    )
    run_parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL,
        help="seconds between status polls (default: 5)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point invoked by console_scripts / CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Flatten the nested list produced by the repeatable --threshold parser.
    thresholds: list[tuple[str, float, str]] = []
    for group in args.thresholds or []:
        thresholds.extend(group)
    args.thresholds = thresholds

    if args.command == "run":
        return run_gate(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
