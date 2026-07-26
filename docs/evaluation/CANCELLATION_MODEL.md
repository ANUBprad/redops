# Cancellation Model

> **Status:** Architecture Design  
> **Depends on:** [STATE_MACHINE.md](STATE_MACHINE.md), [EXECUTION_MODEL.md](EXECUTION_MODEL.md)

---

## 1. Purpose

Cancellation is a first-class operation in the Evaluation Engine. Users can cancel running evaluations at any time. This document defines how cancellation propagates, what happens to in-flight work, and how partial results are preserved.

---

## 2. Cancellation Types

| Type | Trigger | Behavior |
|---|---|---|
| **User Cancel** | API call or UI action | Graceful. Complete current item, then stop. |
| **System Cancel** | Resource pressure, quota exceeded | Graceful. Same as user cancel. |
| **Workflow Cancel** | Temporal workflow cancellation | Graceful. Temporal signals the workflow. |
| **Force Cancel** | API call with `force=true` | Immediate. Abandon current item. |
| **Timeout Cancel** | Workflow duration exceeded | Graceful. Current item completes. |

---

## 3. Cancellation Propagation

### 3.1 Graceful Cancellation Sequence

```
1. User calls POST /evaluations/{run_id}/cancel
2. API layer publishes evaluation.cancel_requested event
3. API layer sends Temporal signal "cancel" to workflow
4. Workflow sets self.is_cancelled = True
5. Workflow checks is_cancelled before next item:
   a. If no item is running:
      - Transition to CANCELLING
      - Skip remaining items
      - Aggregate partial results
      - Persist final state
      - Emit evaluation.cancelled event
      - Complete workflow
   b. If an item is running:
      - Wait for current item to complete
      - Record item result
      - Then skip remaining items
      - Same as (a) from aggregation onward
```

### 3.2 Force Cancellation Sequence

```
1. User calls POST /evaluations/{run_id}/cancel with force=true
2. API layer sends Temporal signal "force_cancel" to workflow
3. Workflow immediately:
   a. Abandon current activity (if possible)
   b. Mark current item as CANCELLED (not FAILED)
   c. Transition to CANCELLING
   d. Skip remaining items
   e. Aggregate partial results
   f. Persist final state
   g. Emit evaluation.cancelled event with force=true
   h. Complete workflow
```

### 3.3 Diagram

```
User                    API                Temporal              Workflow
 │                       │                    │                     │
 │──── POST /cancel ────►│                    │                     │
 │                       │── signal("cancel") ──►                   │
 │                       │                    │── deliver signal ──►│
 │                       │                    │                     │
 │                       │                    │    ┌────────────────┤
 │                       │                    │    │ Check:         │
 │                       │                    │    │ item running?  │
 │                       │                    │    └───┬───────┬────┘
 │                       │                    │        │       │
 │                       │                    │     [no]     [yes]
 │                       │                    │        │       │
 │                       │                    │        │    Wait for
 │                       │                    │        │    item to
 │                       │                    │        │    complete
 │                       │                    │        │       │
 │                       │                    │        ◄───────┘
 │                       │                    │        │
 │                       │                    │    Aggregate
 │                       │                    │    partial results
 │                       │                    │        │
 │                       │                    │    Persist
 │                       │                    │    final state
 │                       │                    │        │
 │                       │                    │    Emit cancelled
 │                       │                    │    event
 │                       │                    │        │
 │◄──── 200 OK ─────────│                    │    Complete
 │                       │                    │    workflow
```

---

## 4. In-Flight Item Handling

### 4.1 Provider Call In Progress

If the provider call is in progress when cancellation is requested:

**Graceful:** Wait for the provider response. The provider call is not cancelled (most providers don't support request cancellation). Record the result. Then stop.

**Force:** Abandon the response. The provider may still complete the call, but the result is discarded. The item is marked as `CANCELLED`.

### 4.2 Metric Computation In Progress

If metric computation is in progress:

**Graceful:** Wait for the metric to complete. Record the result. Then stop.

**Force:** Abandon the metric computation. The metric is recorded as `METRIC_CANCELLED`.

### 4.3 Checkpoint Write In Progress

If a checkpoint write is in progress:

**Graceful:** Wait for the write to complete.

**Force:** Wait for the write to complete (checkpoint writes are fast and critical for recovery).

---

## 5. Partial Results

### 5.1 What Survives Cancellation

| Data | Survives? | Notes |
|---|---|---|
| Completed item results | Yes | All completed items have their results |
| In-progress item result | Depends | Graceful: yes. Force: no. |
| Aggregated metrics | Yes | Computed from available completed items |
| Token usage | Yes | Accumulated from completed items |
| Cost | Yes | Accumulated from completed items |
| Events | Yes | All events up to cancellation are published |

### 5.2 Partial Result Metadata

When a run is cancelled, the final result includes:

```
CancellationMetadata {
    cancelled_at:       datetime
    cancel_reason:      str              # "user_cancelled", "force_cancelled", "timeout"
    force:              bool
    items_completed:    int
    items_remaining:    int
    items_cancelled:    int              # items that were in-progress at cancellation
    partial_results:    bool             # true (always, for cancelled runs)
}
```

### 5.3 Aggregation with Partial Results

Metrics are aggregated from completed items only. The aggregated report includes:

```
AggregatedMetrics {
    ... normal fields ...
    partial_evaluation:     true
    completion_rate:        items_completed / total_items
    data_coverage:          items_completed / total_items
}
```

Consumers of the report can check `partial_evaluation` to determine if results are complete.

---

## 6. Cancellation Idempotency

Cancellation is idempotent. Calling cancel multiple times has the same effect as calling it once.

| Scenario | Behavior |
|---|---|
| Cancel already-completed run | Return 200 (no-op) |
| Cancel already-cancelled run | Return 200 (no-op) |
| Cancel already-failed run | Return 200 (no-op) |
| Cancel during pause | Transition to CANCELLING from PAUSED |
| Cancel during initialization | Transition to CANCELLING from STARTING |

---

## 7. Pause vs Cancel

| Aspect | Pause | Cancel |
|---|---|---|
| Reversible? | Yes (resume) | No |
| Current item | Completes | Completes (graceful) or abandoned (force) |
| Remaining items | Skipped until resume | Skipped permanently |
| State | PAUSED | CANCELLING → COMPLETED (with partial flag) |
| Results | Resumable from checkpoint | Final (partial) |
| Event | `evaluation.paused` | `evaluation.cancelled` |

---

## 8. Cancellation and Cost

Cancelled runs still incur cost for:
- Completed items (provider calls already made)
- Token usage (tokens already consumed)

The cost tracker records:
```
CostAtCancellation {
    total_cost_usd:     float    # cost up to cancellation point
    items_billed:       int      # items that incurred provider cost
    tokens_consumed:    TokenUsage  # tokens consumed up to cancellation
}
```

---

## 9. API Contract

```
POST /api/v1/evaluations/runs/{run_id}/cancel

Request Body:
{
    "reason": "string (optional)",
    "force": false
}

Response:
{
    "run_id": "uuid",
    "status": "cancelling",
    "message": "Cancellation requested. Current item will complete before stopping."
}
```

**Status codes:**
- `200`: Cancellation requested (or already cancelled)
- `404`: Run not found
- `409`: Run is in terminal state (COMPLETED, FAILED, TIMEDOUT)
- `409`: Run is already cancelling
