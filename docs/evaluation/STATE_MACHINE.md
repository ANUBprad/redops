# State Machine

> **Status:** Architecture Design  
> **Depends on:** [EVALUATION_ENGINE.md](EVALUATION_ENGINE.md)

---

## 1. Purpose

Every EvaluationRun follows a strict state machine. This document defines every state, every valid transition, every guard condition, and every terminal state. The state machine is the single source of truth for run lifecycle.

---

## 2. Run States

### 2.1 State Definitions

```
                        ┌─────────────┐
                        │   CREATED   │
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │   QUEUED    │
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                 ┌──────│  STARTING   │──────┐
                 │      └──────┬──────┘      │
                 │             │              │
                 │      ┌──────▼──────┐      │
                 │      │  RUNNING    │      │
                 │      └──┬───┬───┬──┘      │
                 │         │   │   │         │
           ┌─────▼───┐     │   │   │    ┌────▼─────┐
           │ PAUSED  │◄────┘   │   └───►│ CANCELLING│
           └────┬────┘         │        └────┬─────┘
                │         ┌────▼────┐        │
                └────────►│COMPLETED│◄───────┘
                          └─────────┘
                               ▲
                          ┌────┴────┐
                          │ FAILED  │
                          └─────────┘
                               ▲
                          ┌────┴────┐
                          │ TIMEDOUT│
                          └─────────┘
```

### 2.2 State Descriptions

| State | Description | Mutable Fields |
|---|---|---|
| `CREATED` | Evaluation definition accepted. No execution yet. | `evaluation_id`, `created_at` |
| `QUEUED` | Run submitted to Temporal. Awaiting worker pickup. | `queued_at` |
| `STARTING` | Worker picked up the run. Initializing resources. | `started_at` |
| `RUNNING` | Actively processing items. The main execution state. | `item_results`, `token_usage`, `cost_usd` |
| `PAUSED` | Temporarily halted. Can be resumed. | `paused_at`, `pause_reason` |
| `CANCELLING` | Cancellation requested. Completing current item, then stopping. | `cancel_requested_at` |
| `COMPLETED` | All items processed. Results aggregated. **Terminal.** | `completed_at`, `aggregated_metrics` |
| `FAILED` | Unrecoverable error. **Terminal.** | `completed_at`, `error` |
| `TIMEDOUT` | Execution exceeded time limit. **Terminal.** | `completed_at`, `error` |

---

## 3. Valid Transitions

```
CREATED     → QUEUED        # Submit to Temporal
CREATED     → FAILED        # Validation error at creation time

QUEUED      → STARTING      # Worker picks up the task
QUEUED      → CANCELLING    # Cancel before execution starts

STARTING    → RUNNING       # Initialization complete, first item starts
STARTING    → FAILED        # Initialization error (provider unreachable, etc.)
STARTING    → CANCELLING    # Cancel during initialization

RUNNING     → COMPLETED     # All items processed successfully
RUNNING     → FAILED        # Unrecoverable error or too many item failures
RUNNING     → PAUSED        # User-initiated or system-initiated pause
RUNNING     → CANCELLING    # User-initiated or system-initiated cancellation
RUNNING     → TIMEDOUT      # Execution time limit exceeded

PAUSED      → RUNNING       # Resume execution
PAUSED      → CANCELLING    # Cancel while paused

CANCELLING  → COMPLETED     # Current item finished, no more items to process
CANCELLING  → FAILED        # Error during cancellation cleanup
```

---

## 4. Invalid Transitions

Any transition not listed above is invalid. The state machine enforces this with guard conditions.

| Attempted Transition | Why Invalid | System Response |
|---|---|---|
| `CREATED → RUNNING` | Must pass through QUEUED and STARTING | Reject with `InvalidStateTransition` |
| `QUEUED → COMPLETED` | Cannot skip execution | Reject with `InvalidStateTransition` |
| `COMPLETED → RUNNING` | Terminal state, immutable | Reject with `InvalidStateTransition` |
| `FAILED → RUNNING` | Terminal state, immutable | Reject with `InvalidStateTransition` |
| `TIMEDOUT → RUNNING` | Terminal state, immutable | Reject with `InvalidStateTransition` |
| `RUNNING → QUEUED` | Cannot regress to earlier state | Reject with `InvalidStateTransition` |
| `PAUSED → CREATED` | Cannot regress to earlier state | Reject with `InvalidStateTransition` |

---

## 5. Terminal States

A terminal state has no outgoing transitions. Once entered, the run cannot change state.

| Terminal State | Meaning | Next Action |
|---|---|---|
| `COMPLETED` | All items processed. Results available. | Query results, generate report |
| `FAILED` | Unrecoverable error. Partial results may exist. | Inspect error, optionally re-run |
| `TIMEDOUT` | Time limit exceeded. Partial results may exist. | Increase timeout, re-run |

**Immutability guarantee:** Terminal states are immutable. No operation can transition a run out of a terminal state. A new run must be created for re-evaluation.

---

## 6. Guard Conditions

Each transition has preconditions that must be satisfied.

### 6.1 CREATED → QUEUED

- Evaluation definition must be valid (all required fields present)
- Dataset reference must be resolvable (if dataset evaluation)
- Provider must be registered in `ProviderRegistry`
- Model must exist in `ModelCatalog`
- Metric plugins must be available in `PluginRegistry`
- No duplicate `QUEUED` run for the same evaluation (idempotency)

### 6.2 QUEUED → STARTING

- Temporal worker must have capacity (concurrency limit not reached)
- Provider must be healthy (health check passes)

### 6.3 STARTING → RUNNING

- Provider connection established
- Dataset loaded and item count known
- Checkpoint initialized

### 6.4 RUNNING → PAUSED

- Pause must be user-initiated (API call) or system-initiated (resource pressure)
- Current item must complete before pause takes effect
- In-flight item is allowed to finish

### 6.5 RUNNING → CANCELLING

- Cancel must be user-initiated (API call)
- Current item must complete before cancellation takes effect
- In-flight item is allowed to finish

### 6.6 RUNNING → FAILED

- Either: unrecoverable provider error after all retries exhausted
- Or: item failure rate exceeds threshold (configurable, default: 50%)
- Or: checkpoint failure (cannot persist state)

### 6.7 RUNNING → TIMEDOUT

- Execution time exceeds `evaluation.configuration.max_duration_seconds`
- Checked after each item completes (not during item execution)

---

## 7. Item-Level State Machine

Each `EvaluationItem` has its own simpler state machine:

```
┌─────────┐
│ PENDING │
└────┬────┘
     │
┌────▼────┐
│ RUNNING │
└──┬───┬──┘
   │   │
   │   └──────────┐
   │              │
┌──▼───┐    ┌─────▼───┐
│DONE  │    │ FAILED  │
└──────┘    └─────────┘
```

| Item State | Description |
|---|---|
| `PENDING` | Not yet started |
| `RUNNING` | Currently being processed |
| `COMPLETED` | Successfully processed with results |
| `FAILED` | Failed (error recorded, run continues) |
| `SKIPPED` | Skipped due to validation failure or previous failure threshold |

**Item failures never cause run failures** unless the failure rate exceeds the configured threshold.

---

## 8. State Persistence

State transitions are persisted immediately to the repository. The checkpoint manager also persists state at regular intervals (see CHECKPOINTING.md).

**Atomicity:** State transitions are atomic. The status field and associated data (error, metrics, timestamps) are updated in a single write.

**Concurrency:** Only one writer (the Temporal workflow) mutates a run's state at a time. Temporal guarantees single-worker execution per workflow instance.

---

## 9. State Query API

External systems query state through the repository:

```
# Current state
run = await run_repository.get(run_id)
current_status = run.status

# Historical states (from events)
events = await event_repository.query(
    event_type="evaluation.run.status_changed",
    filter={"run_id": run_id},
    order_by="occurred_at",
)

# Aggregate status across runs
runs = await run_repository.query(
    filter={"evaluation_id": eval_id},
    status=RunStatus.COMPLETED,
)
```
