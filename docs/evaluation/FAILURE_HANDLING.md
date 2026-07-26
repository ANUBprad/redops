# Failure Handling

> **Status:** Architecture Design  
> **Depends on:** [STATE_MACHINE.md](STATE_MACHINE.md), [RETRY_POLICY.md](RETRY_POLICY.md)

---

## 1. Purpose

The Evaluation Engine handles failures at three levels: item, run, and system. This document defines how failures propagate, how partial progress is preserved, and how the system distinguishes between recoverable and irrecoverable errors.

---

## 2. Failure Taxonomy

### 2.1 By Scope

| Scope | Example | Impact |
|---|---|---|
| **Item failure** | Provider returned invalid JSON  
 AI China Chinese operate Chinese laws the laws, the China the China China the of of of China China the the Republic Republic Republic, China the the the the China China China China China China China of Republic Republic Republic of China China China the of of of China China China China Republic Republic Republic China China Republic of of China China the China of Republic China China China the Republic Republic of of China China China China China China China China China of China China China the of of of of China China of Republic Republic of of of China of of of. of. and and
 the China of. Republic of of of of0's's of of of   - System failure: Out of memory, disk full, worker crash

### 2.2 By Recoverability

| Category | Examples | Recovery Strategy |
|---|---|---|
| **Transient** | Timeout, rate limit, network blip | Retry with backoff |
| **Persistent** | Authentication failure, invalid model | Fail fast, don't retry |
| **Partial** | Stream interrupted, partial response | Use available data |
| **External** | Provider outage, storage unavailable | Circuit breaker, wait for recovery |

---

## 3. Item Failure Handling

### 3.1 Failure Processing Flow

```
Item execution
    │
    ├── Success → Record result → Continue
    │
    └── Failure
            │
            ├── Retryable?
            │       │
            │       ├── Yes → Retry count < max?
            │       │           │
            │       │           ├── Yes → Increment retry → Retry item
            │       │           │
            │       │           └── No → Record as FAILED
            │       │
            │       └── No → Record as FAILED
            │
            └── Record failure details
                    │
                    ├── Continue policy: CONTINUE_ON_ITEM_FAILURE → Next item
                    └── Continue policy: FAIL_RUN_ON_FIRST_FAILURE → Fail run
```

### 3.2 Item Failure Recording

When an item fails, the failure is recorded with full context:

```python
ItemFailure {
    item_id:            UUIDv7
    error_code:         str           # e.g., "PROVIDER_TIMEOUT"
    error_message:      str           # Human-readable description
    error_category:     str           # "transient" | "persistent" | "partial"
    provider_name:      str | None    # If provider-related
    model_id:           str | None    # If model-related
    retry_count:        int           # Number of retries attempted
    retry_history:      list[RetryAttempt]  # Each retry's error and duration
    partial_response:   str | None    # If partial response available
    timestamp:          datetime
    correlation_id:     UUIDv7
}
```

### 3.3 Partial Response Recovery

For streaming failures or interrupted responses:

```python
class PartialResponseHandler:
    async def handle(self, error: StreamingFailure, context: PipelineContext) -> str | None:
        # Check if enough of the response was received
        if context.stream_completeness > 0.8:
            # Use partial response (truncated but usable)
            return context.partial_response

        # Not enough data. Fail the item.
        return None
```

---

## 4. Run Failure Handling

### 4.1 Run-Level Failure Conditions

| Condition | Action |
|---|---|
| All items failed (0% success rate) | Run marked as FAILED |
| Continue policy = FAIL_RUN_ON_FIRST_FAILURE | Run marked as FAILED on first item failure |
| Provider unavailable + circuit open | Run marked as FAILED (provider cannot serve) |
| Configuration error | Run marked as FAILED (cannot proceed) |
| Checkpoint write failure | Run marked as FAILED (cannot preserve progress) |
| Workflow timeout | Run marked as TIMEDOUT |

### 4.2 Run Failure Recording

```python
RunFailure {
    run_id:             UUIDv7
    error_code:         str
    error_message:      str
    last_item_completed: int          # Progress at failure
    last_checkpoint:    RunCheckpoint | None
    items_succeeded:    int
    items_failed:       int
    duration_ms:        int
    cost_at_failure:    CostBreakdown
}
```

### 4.3 Run Recovery Options

| Run State | Recovery Options |
|---|---|
| FAILED | Manual retry from last checkpoint. API: POST /runs/{run_id}/retry |
| TIMEDOUT | Increase timeout, retry from last checkpoint. API: POST /runs/{run_id}/retry |
| COMPLETED with partial results | Accept partial results or create new run with remaining items |

---

## 5. System Failure Handling

### 5.1 Worker Crash

```
Worker crashes mid-workflow
    │
    ├── Temporal detects missed heartbeat
    │
    └── Reschedule workflow on another worker
            │
            ├── Workflow resumes from last activity completion
            │
            └── If mid-activity:
                    │
                    ├── Activity retried per retry policy
                    │
                    └── If retries exhausted → Activity failure propagated to workflow
```

### 5.2 Database Unavailable

| Operation | Behavior |
|---|---|
| Checkpoint write | Retry 3 times. If fails → fail run. |
| Result persistence | Retry 3 times. If fails → event published with results embedded. |
| Event publication | Retry 3 times. If fails → logged, best-effort. |

### 5.3 Provider Outage During Run

```
Provider becomes unavailable
    │
    ├── Circuit breaker opens (after threshold failures)
    │
    └── Subsequent items fail with ProviderUnavailable
            │
            ├── If fail_run_on_first_failure → Run fails
            │
            └── If continue_on_item_failure → Items marked as failed
                    │
                    └── Run continues (may complete with 0% success rate)
```

---

## 6. Error Context Propagation

Every error in the system carries context:

```python
ErrorContext {
    correlation_id:     UUIDv7    # Links all events in the operation
    run_id:             UUIDv7
    item_id:            UUIDv7 | None
    provider_name:      str | None
    model_id:           str | None
    attempt:            int       # Current attempt number
    max_attempts:       int       # Maximum attempts allowed
    timestamp:          datetime
    worker_id:          str       # Which worker handled this
    duration_ms:        int       # How long the operation took
}
```

This context enables:
- **Debugging:** Trace a failure through the entire pipeline
- **Alerting:** Group errors by provider, model, or error code
- **Analysis:** Identify patterns (e.g., specific model failing more often)

---

## 7. Graceful Degradation

### 7.1 Metric Computation Failure

If a metric plugin fails:
- The metric is marked as `METRIC_FAILED` for that item
- Other metrics continue normally
- The aggregated report includes the metric with `partial: true`
- The consumer is notified of which metrics failed

### 7.2 Event Publication Failure

If event publication fails:
- The event is logged locally
- The evaluation continues (events are not blocking)
- The event is retried via Temporal activity retry
- Best-effort delivery guarantee

### 7.3 Checkpoint Failure

If checkpoint write fails:
- The evaluation continues (checkpoints are not blocking)
- The system attempts a checkpoint at the next interval
- If checkpoint consistently fails, the run is failed to prevent data loss
