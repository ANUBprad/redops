# Checkpointing

> **Status:** Architecture Design  
> **Depends on:** [EXECUTION_MODEL.md](EXECUTION_MODEL.md), [FAILURE_HANDLING.md](FAILURE_HANDLING.md)

---

## 1. Purpose

Checkpoints preserve evaluation progress so that interrupted runs can be resumed from the last saved state rather than restarting from scratch. This document defines what is checkpointed, when checkpoints are created, and how checkpoint data is used for resumption.

---

## 2. Why Checkpoint

| Scenario | Without Checkpoint | With Checkpoint |
|---|---|---|
| Worker crash | Restart evaluation from item 1 | Resume from last checkpoint |
| Provider outage | Lose all progress | Resume from last checkpoint |
| User pause/resume | Not possible | Resume from last checkpoint |
| Run timeout | Start new run from item 1 | Resume from last checkpoint |
| Bug in item N | Must restart from item 1 | Resume from item N+1 |

---

## 3. Checkpoint Contents

### 3.1 Core State

```python
RunCheckpoint {
    run_id:                 UUIDv7
    checkpoint_number:      int           # Sequential (0, 1, 2, ...)
    created_at:             datetime

    # Progress tracking
    items_completed:        int           # Number of completed items
    items_total:            int           # Total items in dataset
    last_item_index:        int           # Index of last completed item

    # Partial results
    completed_items:        list[ItemResult]  # Results for completed items

    # Aggregated state (accumulated so far)
    accumulated_metrics:    dict[str, AggregatedMetrics]
    accumulated_tokens:     TokenUsage
    accumulated_cost:       CostBreakdown

    # Provider state
    provider_call_count:    int
    provider_error_count:   int
    last_provider_error:    str | None
}
```

### 3.2 What is NOT Checkpointed

| Data | Reason |
|---|---|
| Provider connection state | Ephemeral, re-established on resume |
| In-flight item processing | Item will be re-executed on resume |
| Event publication status | Events are idempotent, can be re-published |
| Temporal workflow state | Managed by Temporal, not our concern |

---

## 4. Checkpoint Strategy

### 4.1 Interval-Based Checkpointing

Checkpoints are created at regular intervals during execution:

```
Every N items (default: 50):
    checkpoint_number++
    persist checkpoint to database
    emit evaluation.checkpoint.created event
```

**Default interval:** 50 items (configurable via `evaluation.checkpoint_interval`)

### 4.2 Event-Triggered Checkpointing

Additional checkpoints are created at significant events:

| Trigger | Checkpoint Number |
|---|---|
| Run start | 0 (initial) |
| Every N items | 1, 2, 3, ... |
| Run completion | Final |
| Run failure | Last known good state |
| Run cancellation | State at cancellation |
| Pause | State at pause |

### 4.3 Checkpoint Lifecycle

```
Run starts
    │
    ├── Checkpoint 0 (initial state, no items completed)
    │
    ├── Items 1-50 complete
    │   Checkpoint 1 (50 items, metrics accumulated)
    │
    ├── Items 51-100 complete
    │   Checkpoint 2 (100 items, metrics accumulated)
    │
    ├── Worker crash (items 101-120 lost)
    │
    └── Resume from Checkpoint 2
            │
            ├── Items 101+ re-executed
            │
            └── Checkpoint 3 (120 items, metrics accumulated)
```

---

## 5. Checkpoint Persistence

### 5.1 Storage Location

Checkpoints are stored in the `evaluation_checkpoints` table:

```sql
CREATE TABLE evaluation_checkpoints (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              UUID NOT NULL REFERENCES evaluation_runs(id),
    checkpoint_number   INTEGER NOT NULL,
    checkpoint_data     JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (run_id, checkpoint_number)
);

CREATE INDEX idx_evaluation_checkpoints_run_id ON evaluation_checkpoints(run_id);
```

### 5.2 Retention Policy

| Checkpoint | Retention |
|---|---|
| Latest checkpoint | Permanent (until run is deleted) |
| All previous checkpoints | 30 days |
| Checkpoints for completed runs | 7 days (then pruned, only latest kept) |

### 5.3 Storage Format

Checkpoints are stored as JSONB for queryability:

```json
{
    "run_id": "0192e5f8-...",
    "checkpoint_number": 2,
    "created_at": "2026-07-25T10:30:00Z",
    "items_completed": 100,
    "items_total": 500,
    "last_item_index": 99,
    "completed_items": [...],
    "accumulated_metrics": {...},
    "accumulated_tokens": {"input": 50000, "output": 25000},
    "accumulated_cost": {"total_usd": 1.25}
}
```

---

## 6. Checkpoint Loading

### 6.1 Resume Flow

```
Resume run request
    │
    ├── Load latest checkpoint from database
    │
    ├── Validate checkpoint integrity
    │       │
    │       ├── Checksum valid → Proceed
    │       └── Checksum invalid → Fail (data corruption)
    │
    ├── Reconstruct pipeline state
    │       │
    │       ├── Completed items from checkpoint.completed_items
    │       ├── Accumulated metrics from checkpoint.accumulated_metrics
    │       └── Last item index from checkpoint.last_item_index
    │
    ├── Filter dataset
    │       │
    │       └── Skip items with index <= last_item_index
    │
    └── Resume execution from next unprocessed item
```

### 6.2 Checkpoint Integrity

Each checkpoint includes a checksum:

```python
checkpoint_hash = sha256(
    json.dumps(checkpoint_data, sort_keys=True).encode()
)
```

On load, the checksum is verified. If invalid, the checkpoint is corrupted and the run cannot be resumed from it.

---

## 7. Checkpoint and Metrics

### 7.1 Incremental Metric Aggregation

Metrics are accumulated across checkpoints:

```
Checkpoint 0: {}
Checkpoint 1: {metric_a: [scores for items 1-50]}
Checkpoint 2: {metric_a: [scores for items 1-100]}
Checkpoint 3: {metric_a: [scores for items 1-150]}
```

Each checkpoint contains the complete accumulated state, not just the delta. This simplifies resume logic (load one checkpoint, not all previous ones).

### 7.2 Metric Deduplication

When resuming, items re-executed after the checkpoint are not double-counted:

```python
# On resume
completed_item_ids = {item.item_id for item in checkpoint.completed_items}
for item in dataset:
    if item.item_id in completed_item_ids:
        continue  # Skip already-completed item
    # Process item
```

---

## 8. Checkpoint Performance

### 8.1 Write Latency

Checkpoint writes should not block the evaluation pipeline:

```
Normal execution ──────────────────────────────────────
                        │
Checkpoint write ───────┼────────── (async, non-blocking)
                        │
Next item starts ───────┘
```

Checkpoint writes are performed as Temporal activities. The workflow continues processing items while the checkpoint write happens asynchronously.

### 8.2 Storage Growth

For a 10,000-item evaluation with 50-item checkpoint intervals:
- Checkpoints created: 200
- Average checkpoint size: ~100KB (JSONB)
- Total storage: ~20MB

This is well within acceptable limits for PostgreSQL JSONB storage.

---

## 9. Checkpoint Pruning

### 9.1 Pruning Strategy

Keep only the latest N checkpoints for running evaluations:

```python
# After creating new checkpoint
DELETE FROM evaluation_checkpoints
WHERE run_id = $run_id
AND checkpoint_number < (SELECT MAX(checkpoint_number) - 5
                         FROM evaluation_checkpoints
                         WHERE run_id = $run_id);
```

**Keep:** Latest 5 checkpoints for running evaluations.  
**Keep:** Latest 1 checkpoint for completed/failed evaluations.  
**Delete:** All checkpoints older than 30 days.

### 9.2 Pruning Schedule

Pruning is performed by a scheduled task:

```
Every hour:
    DELETE FROM evaluation_checkpoints
    WHERE created_at < NOW() - INTERVAL '30 days'
    AND checkpoint_number < (
        SELECT MAX(checkpoint_number)
        FROM evaluation_checkpoints ec2
        WHERE ec2.run_id = evaluation_checkpoints.run_id
    );
```

---

## 10. Checkpoint API

```
GET /api/v1/evaluations/runs/{run_id}/checkpoints
    → List checkpoints for a run

GET /api/v1/evaluations/runs/{run_id}/checkpoints/{checkpoint_number}
    → Get specific checkpoint

POST /api/v1/evaluations/runs/{run_id}/resume
    → Resume from latest checkpoint

POST /api/v1/evaluations/runs/{run_id}/resume?from_checkpoint={number}
    → Resume from specific checkpoint
```
