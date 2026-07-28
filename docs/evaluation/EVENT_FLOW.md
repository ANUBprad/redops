# Event Flow

> **Status:** Architecture Design  
> **Depends on:** [EVALUATION_ENGINE.md](EVALUATION_ENGINE.md), [EXECUTION_PIPELINE.md](EXECUTION_PIPELINE.md)

---

## 1. Purpose

The Evaluation Engine publishes domain events throughout the evaluation lifecycle. These events drive observability (dashboards, alerts), integration (webhooks, external systems), and audit (compliance, debugging). This document defines the complete event vocabulary, routing, and consumption patterns.

---

## 2. Event Catalog

### 2.1 Lifecycle Events

| Event | Payload | When |
|---|---|---|
| `evaluation.created` | Evaluation metadata | Evaluation created (no run yet) |
| `evaluation.configured` | Resolved configuration, dataset metadata | Config validated, dataset loaded |
| `evaluation.run_created` | Run metadata, item count | Run initialized |
| `evaluation.run_started` | Run metadata, provider, model | Run begins execution |
| `evaluation.run_paused` | Run metadata, progress | Run paused by user |
| `evaluation.run_resumed` | Run metadata, progress | Run resumed by user |
| `evaluation.run_completed` | Aggregated metrics, duration, cost | Run finished successfully |
| `evaluation.run_failed` | Error details, last checkpoint | Run failed irrecoverably |
| `evaluation.run_timed_out` | Timeout duration, last checkpoint | Run exceeded max duration |
| `evaluation.run_cancelled` | Cancellation metadata, partial results | Run cancelled by user/system |
| `evaluation.run_deleted` | Run metadata | Run soft-deleted |

### 2.2 Item Events

| Event | Payload | When |
|---|---|---|
| `evaluation.item.started` | Item metadata, template context | Item processing begins |
| `evaluation.item.completed` | Item result, metrics, tokens | Item processing finished |
| `evaluation.item.failed` | Item error, retry info | Item failed (may be retried) |
| `evaluation.item.retried` | Item metadata, retry count, previous error | Item retry started |
| `evaluation.item.cancelled` | Item metadata, cancellation reason | Item abandoned due to cancellation |
| `evaluation.item.skipped` | Item metadata, skip reason | Item skipped (e.g., cache hit, dedup) |

### 2.3 Provider Events

| Event | Payload | When |
|---|---|---|
| `evaluation.provider.invoked` | Provider name, model, request metadata | Provider call started |
| `evaluation.provider.completed` | Provider name, response metadata, tokens | Provider call succeeded |
| `evaluation.provider.failed` | Provider name, error details | Provider call failed |
| `evaluation.provider.timeout` | Provider name, timeout duration | Provider call timed out |
| `evaluation.provider.rate_limited` | Provider name, retry_after | Rate limit encountered |
| `evaluation.provider.circuit_open` | Provider name, failure count | Circuit breaker opened |
| `evaluation.provider.circuit_closed` | Provider name | Circuit breaker closed |

### 2.4 Metric Events

| Event | Payload | When |
|---|---|---|
| `evaluation.metric.computed` | Metric name, score, item_id | One metric computed for one item |
| `evaluation.metric.failed` | Metric name, item_id, error | Metric computation failed |
| `evaluation.metric.aggregated` | Metric name, aggregated score, count | Metric aggregated across items |

### 2.5 Checkpoint Events

| Event | Payload | When |
|---|---|---|
| `evaluation.checkpoint.created` | Checkpoint metadata, item range | Checkpoint persisted |
| `evaluation.checkpoint.loaded` | Checkpoint metadata, resume point | Checkpoint loaded for resume |

### 2.6 System Events

| Event | Payload | When |
|---|---|---|
| `evaluation.system.worker_registered` | Worker ID, capabilities | New worker joined task queue |
| `evaluation.system.worker_deregistered` | Worker ID, reason | Worker left task queue |
| `evaluation.system.health_changed` | Component, old_status, new_status | System health status changed |

---

## 3. Event Structure

```python
@dataclass(frozen=True)
class EvaluationEvent:
    event_id:        UUIDv7        # Unique, time-ordered
    event_type:      str           # e.g., "evaluation.item.completed"
    timestamp:       datetime      # UTC, microseconds
    correlation_id:  UUIDv7        # Links all events in a run
    run_id:          UUIDv7        # Links events to a specific run
    item_id:         UUIDv7 | None # Links events to a specific item (None for run-level events)
    payload:         dict[str, Any]  # Event-specific data
    metadata:        EventMetadata # Source, version, etc.

@dataclass(frozen=True)
class EventMetadata:
    source:          str           # e.g., "evaluation-engine"
    version:         str           # e.g., "1.0"
    producer_id:     str           # Worker or process ID
```

---

## 4. Event Routing

### 4.1 Event Bus Integration

Events flow through the Kernel's `EventBus`:

```
EvaluationEngine
    │
    ▼
EventBus.publish(event)
    │
    ├──► ConsoleEventHandler (dev, logs to console)
    ├──► DatabaseEventHandler (persists to events table)
    ├──► MetricsEventHandler (feeds Prometheus metrics)
    └──► WebhookEventHandler (if webhook configured)
```

### 4.2 Event Filtering

Consumers can subscribe to specific event types:

```python
# Subscribe to all run-level events
event_bus.subscribe("evaluation.run.*", handler)

# Subscribe to item failures only
event_bus.subscribe("evaluation.item.failed", handler)

# Subscribe to provider errors
event_bus.subscribe("evaluation.provider.*", handler)
```

### 4.3 Event Ordering

Events are ordered by `event_id` (UUIDv7 timestamp). However:
- Events from different items may interleave (parallel execution)
- Events from the same item are strictly ordered
- Consumers must not assume total ordering across items

---

## 5. Event Consumers

### 5.1 Real-Time Dashboard

Subscribes to lifecycle and item events to update live progress.

```
evaluation.run_started     → Show run in "Running" state
evaluation.item.completed  → Increment progress bar
evaluation.run_completed   → Show final results
```

### 5.2 Webhook Integration

Forwards events to external systems:

```python
webhook_config = {
    "url": "https://external-system.com/api/evaluations",
    "events": ["evaluation.run_completed", "evaluation.run_failed"],
    "headers": {"Authorization": "Bearer ..."},
    "retry": 3,
}
```

### 5.3 Audit Log

Persists all events to an append-only audit log for compliance.

### 5.4 Metrics Export

Converts events to Prometheus metrics:

```
evaluation_runs_total{status="completed"}  42
evaluation_runs_total{status="failed"}     3
evaluation_items_total{status="completed"} 1234
evaluation_provider_latency_seconds{provider="openai", quantile="0.95"} 2.3
evaluation_tokens_total{provider="openai", model="gpt-4"} 456789
evaluation_cost_usd_total{provider="openai"} 12.34
```

---

## 6. Event Publication Pattern

Events are published via Temporal activities to ensure durability:

```
# In workflow
await workflow.execute_activity(
    EmitEventActivity,
    args=[evaluation.item.completed, payload],
    start_to_close_timeout=timedelta(seconds=10),
    retry_policy=RetryPolicy(maximum_attempts=3),
)
```

**Rationale:** Event publication is a side effect. Using a Temporal activity ensures:
- Events are published exactly once (Temporal deduplication)
- Events survive worker crashes (Temporal persistence)
- Events are retried if publication fails (Temporal retry)

---

## 7. Event Versioning

Events use semantic versioning:

```
evaluation.item.completed.v1    → Initial version
evaluation.item.completed.v2    → Added retry_count field
```

Consumers must handle unknown fields gracefully. Version transitions are additive (new fields only, no removals).
