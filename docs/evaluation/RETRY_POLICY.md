# Retry Policy

> **Status:** Architecture Design  
> **Depends on:** [FAILURE_HANDLING.md](FAILURE_HANDLING.md), [EXECUTION_MODEL.md](EXECUTION_MODEL.md)

---

## 1. Purpose

The retry policy determines when and how failed operations are retried. It balances resilience (recovering from transient failures) against resource conservation (not retrying permanent failures).

---

## 2. Retryable vs Non-Retryable Errors

### 2.1 Retryable Errors

| Error | Reason | Max Retries |
|---|---|---|
| `ProviderTimeout` | Transient network or load issue | 3 |
| `RateLimitExceeded` | Temporary rate limit window | 5 (with rate-limit-aware backoff) |
| `ProviderUnavailable` | Provider temporarily down | 3 |
| `StreamingFailure` | Stream interrupted mid-response | 2 |
| `NetworkError` | DNS, connection, or TLS failure | 3 |
| `StorageTimeout` | Database temporary slowdown | 3 |

### 2.2 Non-Retryable Errors

| Error | Reason | Action |
|---|---|---|
| `AuthenticationRequired` | Invalid API key | Fail run |
| `InvalidModel` | Model name wrong | Fail run |
| `ContextWindowExceeded` | Input too large | Fail item |
| `TokenLimitExceeded` | Max tokens too large | Fail item |
| `ValidationError` | Invalid configuration | Fail run |
| `ConfigurationError` | Missing required config | Fail run |

### 2.3 Ambiguous Errors

Some errors require context-dependent retry decisions:

| Error | Default | Override |
|---|---|---|
| `ContextWindowExceeded` | Fail item | If `truncation_enabled`, truncate and retry once |
| `StreamingFailure` | Retry once | If stream was > 80% complete, use partial result |
| Provider 500 error | Retry once | If provider reports specific code, may be non-retryable |

---

## 3. Backoff Strategies

### 3.1 Exponential Backoff (Default)

```
delay = min(initial_interval * (backoff_coefficient ^ attempt), max_interval)
actual_delay = delay * (1 + random_jitter)
```

**Default parameters:**
- `initial_interval`: 1 second
- `backoff_coefficient`: 2.0
- `max_interval`: 60 seconds
- `jitter`: ±25%

**Retry sequence:** 1s → 2s → 4s → 8s → 16s → 32s → 60s (capped)

### 3.2 Rate-Limit-Aware Backoff

When `RateLimitExceeded` includes `retry_after_seconds`:

```
delay = retry_after_seconds * (1 + random_jitter)
```

If `retry_after_seconds` is not provided, fall back to exponential backoff starting at 5s.

### 3.3 Provider-Specific Backoff

Some providers have known retry semantics:

| Provider Behavior | Backoff Strategy |
|---|---|
| Returns `Retry-After` header | Use header value |
| Returns 429 with `x-ratelimit-reset` | Wait until reset time |
| Returns 503 (overloaded) | Exponential backoff starting at 2s |
| Connection reset | Exponential backoff starting at 1s |

---

## 4. Maximum Attempts

### 4.1 Activity-Level Retry

Each Temporal activity has its own retry policy:

| Activity | Max Attempts | Backoff |
|---|---|---|
| `InvokeProviderActivity` | 3 | Exponential, 1s initial |
| `CheckpointActivity` | 3 | Exponential, 1s initial |
| `EmitEventActivity` | 3 | Exponential, 0.5s initial |
| `LoadDatasetActivity` | 3 | Exponential, 2s initial |
| `InitializeRunActivity` | 3 | Exponential, 1s initial |
| `ComputeMetricActivity` | 1 | No retry |
| `RenderTemplateActivity` | 1 | No retry |
| `ParseResponseActivity` | 1 | No retry |

### 4.2 Item-Level Retry

Individual evaluation items may be retried if the failure is retryable:

```
item_retry_policy {
    max_retries:            3
    retryable_errors:       [ProviderTimeout, RateLimitExceeded, ProviderUnavailable]
    non_retryable_errors:   [AuthenticationRequired, InvalidModel, ContextWindowExceeded]
    backoff:                exponential(1s, 2.0, 60s)
}
```

### 4.3 Run-Level Retry

The run itself is not retried. If a run fails, a new run must be created. The checkpoint enables resuming the failed run, but this is a manual or API-driven action, not automatic.

---

## 5. Idempotency Requirements

### 5.1 Provider Invocations

Provider chat calls are **not inherently idempotent**. Retrying a chat call may produce different results. However:

- The retry is for **transient failures** (timeout, rate limit). If the call failed, the provider likely didn't process it.
- If the provider processed the request but the response was lost, retrying produces a **different response** but the evaluation is still valid (different random seed or timing).
- The evaluation records `retry_count` on each item, enabling analysis of retry impact.

### 5.2 Checkpoint Writes

Checkpoint writes are **idempotent**. Writing the same checkpoint data twice produces the same result (upsert by `run_id + checkpoint_number`).

### 5.3 Event Publications

Events are **idempotent by `event_id`**. Publishing the same event twice is detected by the consumer (UUIDv7 deduplication).

### 5.4 Result Persistence

Result writes are **idempotent**. Results are upserted by `item_id`. Writing the same result twice produces the same record.

---

## 6. Retry Monitoring

### 6.1 Metrics to Track

| Metric | Description | Alert Threshold |
|---|---|---|
| `retry.count` | Total retries across all items | > 10% of total items |
| `retry.rate` | retries / total invocations | > 5% warning |
| `retry.provider_timeout` | Retries due to timeout | > 20% of items |
| `retry.rate_limit` | Retries due to rate limiting | > 10% of items |
| `retry.exhausted` | Retries failed after max attempts | Any occurrence |

### 6.2 Retry Impact Analysis

Each `ItemResult` includes:
- `retry_count`: Number of retries for this item
- `retry_history`: List of retry attempts with timestamps and error codes
- `total_retry_duration_ms`: Cumulative time spent in retries

This data enables post-evaluation analysis of retry impact on:
- Total evaluation duration
- Cost (retries consume tokens)
- Result quality (retries may produce different outputs)

---

## 7. Circuit Breaker Integration

The Kernel's `CircuitBreaker` is used for provider calls:

```
ProviderCircuitBreaker {
    failure_threshold:      5       # open after 5 consecutive failures
    recovery_timeout:       30s     # try again after 30s
    half_open_max_calls:    1       # test with 1 call
    expected_exception:     ProviderException
}
```

**Behavior:**
- **Closed:** Normal operation. Failures counted.
- **Open:** All calls fail-fast with `ProviderUnavailable`. No actual provider call.
- **Half-Open:** One test call. If succeeds → Closed. If fails → Open.

**Purpose:** Prevents overwhelming a failing provider with retry attempts. Gives the provider time to recover.
