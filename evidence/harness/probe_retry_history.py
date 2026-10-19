"""Minimal probe: what does a real Temporal retry look like in history?

Runs a trivial workflow with one activity that fails on attempt 1 and succeeds
on attempt 2 under an explicit retry policy, then dumps the ordered event list
so we can state precisely how the server records a retry.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from google.protobuf.json_format import MessageToDict
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.worker import Worker

ADDRESS = "localhost:57233"
TQ = "redops-verify-tq"

CALLS = {"n": 0}


@activity.defn(name="probe_activity")
async def probe_activity() -> str:
    CALLS["n"] += 1
    if CALLS["n"] == 1:
        raise RuntimeError("probe transient failure on attempt 1")
    return "ok"


@workflow.defn(name="ProbeRetryWorkflow")
class ProbeRetryWorkflow:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(
            probe_activity,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
            ),
        )


async def main() -> int:
    client = await Client.connect(ADDRESS, namespace="default")
    worker = Worker(client, task_queue=TQ, workflows=[ProbeRetryWorkflow], activities=[probe_activity])
    async with worker:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        handle = await client.start_workflow(ProbeRetryWorkflow.run, id=f"redops-probe-retry-{ts}", task_queue=TQ)
        result = await handle.result()
        history = await handle.fetch_history()
        events = [MessageToDict(e, preserving_proto_field_name=True) for e in history.events]
    out = {
        "result": result,
        "worker_side_call_count": CALLS["n"],
        "events": [
            {"event_id": e["event_id"], "event_type": e["event_type"],
             **{k: v for k, v in e.items() if k.endswith("_event_attributes")}}
            for e in events
        ],
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
