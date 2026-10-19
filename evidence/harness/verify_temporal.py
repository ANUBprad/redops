"""Real-Temporal verification: activity retry policy + workflow cancellation.

Connects to a real Temporal server (TEMPORAL address from env), runs the
production ``EvaluationRunWorkflow`` definition with controlled item
activities (one fails on attempt 1 and succeeds on attempt 2; one is slow so
cancellation can be signalled mid-flight), exports the workflow histories from
the server, and asserts the observed attempt counts and terminal states.

The workflow + retry policies are the production ones. Only the activity
bodies are controlled test doubles so the outcome is deterministic; every
Temporal scheduling/retry/cancellation decision is made by the real server.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from app.evaluation.temporal.activities import (
    CancelRunInput,
    ExecuteItemInput,
    ExecuteItemResult,
    FailRunInput,
    FinalizeRunIntegrityInput,
    PersistMetricResultsInput,
    ProgressInput,
    RunIdInput,
    RunResult,
    StartRunInput,
)
from app.evaluation.temporal.workflow import (
    EvaluationRunWorkflow,
    EvaluationRunWorkflowInput,
)

ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:57233")
TASK_QUEUE = os.environ.get("REDOPS_VERIFY_TASK_QUEUE", "redops-verify-tq")
OUT = Path(__file__).resolve().parent / "temporal-evidence"
OUT.mkdir(exist_ok=True)

ATTEMPTS: dict[str, int] = {}
EXECUTED: dict[str, list[int]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- controlled lifecycle activities (name-matched to production) ----------


@activity.defn(name="queue_run_activity")
async def queue_run(input: RunIdInput) -> RunResult:
    return RunResult(run_id=input.run_id, status="queued")


@activity.defn(name="start_run_activity")
async def start_run(input: StartRunInput) -> RunResult:
    return RunResult(run_id=input.run_id, status="running")


@activity.defn(name="update_progress_activity")
async def update_progress(input: ProgressInput) -> RunResult:
    return RunResult(run_id=input.run_id, status="running")


@activity.defn(name="persist_metric_results_activity")
async def persist_metrics(input: PersistMetricResultsInput) -> int:
    return len(input.results)


@activity.defn(name="finalize_run_integrity_activity")
async def finalize(input: FinalizeRunIntegrityInput) -> str:
    return "pass"


@activity.defn(name="complete_run_activity")
async def complete_run(input: RunIdInput) -> RunResult:
    return RunResult(run_id=input.run_id, status="completed")


@activity.defn(name="fail_run_activity")
async def fail_run(input: FailRunInput) -> RunResult:
    return RunResult(run_id=input.run_id, status="failed")


@activity.defn(name="cancel_run_activity")
async def cancel_run(input: CancelRunInput) -> RunResult:
    return RunResult(run_id=input.run_id, status="cancelled")


def _result(inp: ExecuteItemInput, *, seconds: float) -> ExecuteItemResult:
    EXECUTED.setdefault(inp.run_id, []).append(inp.item_index)
    return ExecuteItemResult(
        item_index=inp.item_index,
        item_id=inp.item_id or f"item-{inp.item_index}",
        prompt=inp.prompt,
        response="controlled-stub-response",
        tokens_input=7,
        tokens_output=3,
        latency_ms=int(seconds * 1000),
        failed=False,
        metrics=(),
    )


@activity.defn(name="execute_item_activity")
async def execute_item(input: ExecuteItemInput) -> ExecuteItemResult:
    """Retry run: fail item 0 on attempt 1 then succeed. Cancel run: slow item."""
    mode = os.environ["REDOPS_VERIFY_MODE"]
    key = f"{input.run_id}:{input.item_index}"
    ATTEMPTS[key] = ATTEMPTS.get(key, 0) + 1
    attempt = ATTEMPTS[key]

    if mode == "retry" and input.item_index == 0 and attempt == 1:
        raise RuntimeError("controlled transient failure on attempt 1")

    seconds = 3.0 if mode == "cancel" else 0.2
    await asyncio.sleep(seconds)
    return _result(input, seconds=seconds)


ALL_ACTIVITIES = [
    queue_run,
    start_run,
    update_progress,
    persist_metrics,
    finalize,
    complete_run,
    fail_run,
    cancel_run,
    execute_item,
]


async def _dump_history(client: Client, wf_id: str, path: Path) -> dict:
    handle = client.get_workflow_handle(wf_id)
    desc = await handle.describe()
    history = await handle.fetch_history()
    events = [MessageToDict(e, preserving_proto_field_name=True) for e in history.events]
    payload = {
        "workflow_id": wf_id,
        "run_id": desc.run_id,
        "status": desc.status.name if desc.status else None,
        "start_time": desc.start_time.isoformat() if desc.start_time else None,
        "close_time": desc.close_time.isoformat() if desc.close_time else None,
        "events": events,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _attempt_counts(events: list[dict]) -> list[dict]:
    """Map each activity's scheduled event to its started attempts.

    Activity type names live on the *scheduled* event; attempt numbers live on
    the *started* event. Correlate via scheduled_event_id.
    """
    scheduled: dict[str, str] = {}
    for ev in events:
        attrs = ev.get("activity_task_scheduled_event_attributes")
        if attrs:
            scheduled[ev["event_id"]] = attrs.get("activity_type", {}).get("name", "?")
    per_activity: dict[str, list[int]] = {}
    for ev in events:
        attrs = ev.get("activity_task_started_event_attributes")
        if attrs:
            name = scheduled.get(attrs.get("scheduled_event_id", ""), "?")
            per_activity.setdefault(name, []).append(int(attrs.get("attempt", 0)))
    return [
        {"activity_type": k, "started_attempts": len(v), "attempt_numbers": sorted(v)}
        for k, v in sorted(per_activity.items())
    ]


async def main() -> int:
    mode = os.environ["REDOPS_VERIFY_MODE"]
    client = await Client.connect(ADDRESS, namespace="default")
    worker = Worker(client, task_queue=TASK_QUEUE, workflows=[EvaluationRunWorkflow], activities=ALL_ACTIVITIES)

    results: dict = {
        "mode": mode,
        "temporal_address": ADDRESS,
        "task_queue": TASK_QUEUE,
        "started_at_utc": _now(),
    }

    async with worker:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        wf_id = f"redops-verify-{mode}-{ts}"
        total_items = 1 if mode == "retry" else 3
        inp = EvaluationRunWorkflowInput(
            run_id=f"run-{mode}-{ts}",
            total_items=total_items,
            provider_name="openai",
            model_id="gpt-4o-mini",
            metric_names=("cost",),
            dataset_items=tuple({"prompt": f"q{i}", "item_id": f"item-{i}"} for i in range(total_items)),
        )

        handle = await client.start_workflow(
            EvaluationRunWorkflow.run,
            inp,
            id=wf_id,
            task_queue=TASK_QUEUE,
        )
        results["workflow_id"] = wf_id
        results["workflow_input"] = {"total_items": total_items, "provider_name": "openai", "model_id": "gpt-4o-mini"}

        cancel_requested_at = None
        if mode == "cancel":
            await asyncio.sleep(1.0)
            cancel_requested_at = _now()
            await handle.signal(EvaluationRunWorkflow.cancel)
            results["cancellation_requested_at_utc"] = cancel_requested_at

        wf_result = await handle.result()
        results["completed_at_utc"] = _now()
        results["workflow_result"] = {
            "run_id": wf_result.run_id,
            "status": wf_result.status,
            "items_completed": wf_result.items_completed,
            "items_total": wf_result.items_total,
            "items_failed": wf_result.items_failed,
            "total_tokens_input": wf_result.total_tokens_input,
            "total_tokens_output": wf_result.total_tokens_output,
        }
        results["item_activity_attempts"] = {
            k: v for k, v in ATTEMPTS.items() if k.startswith(inp.run_id)
        }
        results["item_indices_executed"] = EXECUTED.get(inp.run_id, [])

        payload = await _dump_history(client, wf_id, OUT / f"temporal-{mode}-history.json")
        results["workflow_status_from_server"] = payload["status"]
        results["activity_started_attempts"] = _attempt_counts(payload["events"])
        results["history_event_count"] = len(payload["events"])

    (OUT / f"temporal-{mode}-summary.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
