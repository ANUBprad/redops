# Execution Model

> **Status:** Architecture Design  
> **Depends on:** [EVALUATION_ENGINE.md](EVALUATION_ENGINE.md), [EXECUTION_PIPELINE.md](EXECUTION_PIPELINE.md)

---

## 1. Purpose

The Evaluation Engine uses Temporal for workflow orchestration. This document defines the workflow and activity decomposition, signal handling, query handling, and the mapping between engine concepts and Temporal primitives.

---

## 2. Why Temporal

| Requirement | How Temporal Addresses It |
|---|---|
| Durability | Workflow state persisted to Temporal's database. Survives worker crashes. |
| Automatic retries | Activity retry policies with exponential backoff. |
| Timeout management | Workflow and activity-level timeouts. |
| Visibility | Temporal UI shows running/completed/failed workflows. |
| Signaling | Pause/resume/cancel via Temporal signals. |
| Versioning | Workflow versioning for safe deployments. |
| Concurrency | Task queue with configurable worker concurrency. |

**Alternatives considered:**
- **Celery:** Lacks durable execution. No built-in workflow versioning. Retry semantics less mature.
- **Redis Queue:** No durable execution. Manual checkpointing required. No signal support.
- **Custom orchestration:** Reimplements everything Temporal provides. High maintenance burden.

**Tradeoff:** Temporal adds operational complexity (worker management, namespace configuration). The durability and reliability guarantees outweigh this cost for a production evaluation platform.

---

## 3. Workflow Decomposition

### 3.1 One Workflow Per Run

Each `EvaluationRun` maps to one Temporal workflow instance.

```
Workflow ID:    evaluation-run-{run_id}
Task Queue:     redops-eval
Workflow:       EvaluationRunWorkflow
```

**Rationale:** One-workflow-per-run provides natural isolation. Each run has its own state, retry policy, and timeout. Cancellation of one run doesn't affect others.

### 3.2 Workflow Structure

```
EvaluationRunWorkflow {
    # Input
    run_id:         UUIDv7
    evaluation:     Evaluation

    # Workflow execution
    1. Initialize from checkpoint (or fresh start)
    2. Load dataset
    3. Partition dataset (if parallel)
    4. For each partition (or sequentially):
         For each item in partition:
             ExecuteItem activity
         CheckpointPartition activity
     AggregateResults activity
     PersistFinalResults activity
}
```

### 3.3 Workflow Signals

| Signal | Payload | Effect |
|---|---|---|
| `pause` | `{reason: str}` | Sets pause flag. Current item completes, then workflow pauses. |
| `resume` | `{}` | Clears pause flag. Workflow resumes from checkpoint. |
| `cancel` | `{reason: str}` | Sets cancel flag. Current item completes, then workflow terminates. |
| `update_config` | `{config: dict}` | Updates runtime configuration (e.g., concurrency limit). |

### 3.4 Workflow Queries

| Query | Returns | Purpose |
|---|---|---|
| `get_status` | `RunStatus` | Current run status |
| `get_progress` | `{completed: int, total: int, percent: float}` | Progress tracking |
| `get_metrics` | `AggregatedMetrics` | Live metric aggregation |
| `get_checkpoint` | `RunCheckpoint` | Latest checkpoint |

---

## 4. Activity Decomposition

### 4.1 Activity Inventory

| Activity | Purpose | Timeout | Retry |
|---|---|---|---|
| `InitializeRunActivity` | Load evaluation, resolve provider, load dataset | 60s | 3 retries |
| `LoadDatasetActivity` | Fetch dataset rows from storage | 120s | 3 retries |
| `RenderTemplateActivity` | Render prompt template with item variables | 5s | 1 retry |
| `InvokeProviderActivity` | Call provider.chat() through contract | Per-provider timeout | Per-provider retry |
| `ParseResponseActivity` | Validate and normalize provider response | 5s | 1 retry |
| `ComputeMetricActivity` | Execute one metric plugin | 30s | 1 retry |
| `CheckpointActivity` | Persist checkpoint to database | 30s | 3 retries |
| `AggregateResultsActivity` | Aggregate metric scores across items | 60s | 2 retries |
| `PersistResultsActivity` | Write final results to database | 60s | 3 retries |
| `EmitEventActivity` | Publish domain event to Event Bus | 10s | 3 retries |

### 4.2 Activity Design Principles

1. **One activity per side effect.** Each activity performs one discrete operation. This enables precise retry and timeout control.

2. **Activities are idempotent.** Retrying an activity produces the same result. The activity checks for existing results before writing.

3. **Activities carry correlation context.** Every activity receives `correlation_id` and `run_id` for tracing.

4. **Activities publish their own events.** The `EmitEventActivity` is called by the workflow after each significant state change.

### 4.3 Activity Execution Pattern

```
# Inside workflow
for item in items:
    # Check pause/cancel before each item
    if self.is_paused:
        await workflow.wait_condition(lambda: not self.is_paused)
    if self.is_cancelled:
        break

    # Execute item through activities
    context = await workflow.execute_activity(
        RenderTemplateActivity,
        args=[item, profile],
        start_to_close_timeout=timedelta(seconds=5),
    )

    response = await workflow.execute_activity(
        InvokeProviderActivity,
        args=[context, provider_name, model_id],
        start_to_close_timeout=timedelta(seconds=profile.timeout_seconds),
        retry_policy=RetryPolicy(
            maximum_attempts=3,
            backoff_coefficient=2.0,
            initial_interval=timedelta(seconds=1),
        ),
    )

    # ... remaining stages ...

    # Checkpoint after N items
    if items_completed % checkpoint_interval == 0:
        await workflow.execute_activity(
            CheckpointActivity,
            args=[run_id, checkpoint_data],
            start_to_close_timeout=timedelta(seconds=30),
        )
```

---

## 5. Workflow Versioning

### 5.1 Version Strategy

Temporal workflow versioning is used for safe deployments. When the workflow logic changes:

1. **New version number** is assigned
2. **Version check** is placed at the point of change
3. **Existing workflows** continue with the old version
4. **New workflows** start with the new version

```python
# Example: changing checkpoint interval
version = workflow.get_version(
    "checkpoint-interval",
    from_version=1,
    to_version=2,
)
if version >= 2:
    checkpoint_interval = new_checkpoint_interval
else:
    checkpoint_interval = old_checkpoint_interval
```

### 5.2 Version Compatibility Rules

| Change Type | Version Required | Migration |
|---|---|---|
| New activity added | Yes | Old workflows skip new activity |
| Activity signature changed | Yes | New activity with version check |
| Workflow logic changed | Yes | Version check at branch point |
| New signal added | No | Old workflows ignore unknown signals |
| Activity timeout changed | No | Temporal handles gracefully |

---

## 6. Concurrency Model

### 6.1 Workflow Concurrency

Each workflow instance is single-threaded. Activities execute sequentially within a workflow. Parallelism is achieved through:

1. **Multiple workflow instances** (one per evaluation run)
2. **Activity options** (Temporal supports activity retry concurrency)
3. **Child workflows** (for partitioned dataset processing)

### 6.2 Activity Concurrency

Temporal worker concurrency is configured via:

```python
TemporalConfiguration {
    max_concurrent_activities:     100    # activities across all workflows
    max_concurrent_workflow_tasks: 10    # workflow task processing
    max_concurrent_local_activities: 10  # local activities
}
```

### 6.3 Dataset Partitioning for Parallelism

For large datasets, the workflow partitions data and processes partitions via child workflows:

```
EvaluationRunWorkflow
  ├── ChildWorkflow: Partition 1 (items 1-1000)
  ├── ChildWorkflow: Partition 2 (items 1001-2000)
  ├── ChildWorkflow: Partition 3 (items 2001-3000)
  └── AggregateResults (waits for all children)
```

See PARALLEL_EXECUTION.md for partitioning details.

---

## 7. Timeout Architecture

```
┌─────────────────────────────────────────────────┐
│              Workflow Timeout                    │
│  (evaluation.configuration.max_duration_seconds) │
│                                                  │
│  ┌───────────────────────────────────────────┐   │
│  │         Activity Timeouts                 │   │
│  │                                           │   │
│  │  Provider:  profile.timeout_seconds       │   │
│  │  Metrics:   30s per metric                │   │
│  │  Checkpoint: 30s                          │   │
│  │  Init:      60s                           │   │
│  │  Aggregate: 60s                           │   │
│  └───────────────────────────────────────────┘   │
│                                                  │
│  ┌───────────────────────────────────────────┐   │
│  │         Heartbeat Timeout                 │   │
│  │  (for long-running activities)            │   │
│  │                                           │   │
│  │  Provider: 30s heartbeat interval         │   │
│  └───────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

---

## 8. Failure Handling in Temporal

### 8.1 Activity Failure

When an activity fails:
1. Temporal checks the activity's retry policy
2. If retries remain, the activity is rescheduled
3. If retries exhausted, the activity failure is propagated to the workflow
4. The workflow handles the failure (fail item, continue, or fail run)

### 8.2 Workflow Failure

When the workflow fails:
1. Temporal marks the workflow as FAILED
2. The `evaluation.failed` event is emitted
3. Checkpoint is preserved for potential manual recovery
4. The run's error details are persisted

### 8.3 Worker Crash

When a worker crashes:
1. Temporal detects the missed heartbeat
2. Temporal reschedules the workflow on another worker
3. The workflow resumes from the last activity completion
4. If the workflow was mid-activity, the activity is retried

---

## 9. Local Activities

For operations that don't need Temporal's durability (e.g., template rendering, response parsing), local activities are used:

```
LocalActivity {
    # No retry (idempotent by design)
    # No heartbeat
    # Executes on the workflow worker
    # Lower latency (no task queue round-trip)
}
```

Use local activities for:
- Template rendering
- Response parsing
- Output validation
- Metric computation (if metric is pure)

Use regular activities for:
- Provider invocation (needs retry + timeout)
- Checkpoint persistence (needs durability)
- Event publication (needs reliability)

---

## 10. Worker Configuration

```python
TemporalWorkerConfiguration {
    task_queue:                     "redops-eval"
    max_concurrent_workflow_tasks:  10
    max_concurrent_activities:      100
    max_concurrent_local_activities: 50
    graceful_shutdown_timeout:      30 seconds
    workflow_task_timeout:          10 seconds
}
```

**Scaling:** Add workers to increase throughput. Temporal automatically distributes workflow tasks across available workers.
