# Provider Runtime

Orchestration layer between the Evaluation Engine and concrete provider implementations.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  RuntimeCoordinator                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │  Retry   │  │ Circuit  │  │    Rate Limit     │  │
│  │Evaluator │  │ Breaker  │  │    (SlidingWindow)│  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Timeout  │  │ Fallback │  │  MiddlewarePipeline│  │
│  │Evaluator │  │  Chain   │  │                   │  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │  Cache   │  │ Telemetry│  │  HealthAggregator │  │
│  │ (LRU)   │  │          │  │                   │  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Components

| Package | Purpose | Key Classes |
|---------|---------|-------------|
| `context` | Immutable execution context | `ExecutionContext`, `CancellationToken`, `ExecutionBudget` |
| `errors` | Typed error hierarchy | `RuntimeBaseError`, `CircuitBreakerOpenError`, `RetryExhaustedError`, etc. |
| `events` | Runtime domain events | `ExecutionRequested`, `RetryScheduled`, `CircuitOpened`, etc. |
| `policies` | Immutable configuration | `RetryPolicy`, `TimeoutPolicy`, `FallbackPolicy`, `ExecutionPolicy` |
| `retry` | Retry decisions | `RetryEvaluator`, `RetryDecision`, `RetryContext` |
| `circuit_breaker` | Circuit breaking | `RuntimeCircuitBreaker`, `CircuitBreakerConfig` |
| `rate_limit` | Rate limiting | `SlidingWindowRateLimiter`, `RateLimitResult` |
| `timeout` | Timeout enforcement | `TimeoutEvaluator`, `TimeoutResult` |
| `fallback` | Provider fallback | `FallbackChain`, `FallbackDecision`, `FallbackEntry` |
| `middleware` | Before/after hooks | `RuntimeMiddleware`, `MiddlewarePipeline`, `MiddlewareContext` |
| `cache` | Response caching | `RuntimeCache`, `CacheConfig`, `CacheStats` |
| `telemetry` | Observability | `RuntimeTelemetry`, `CompletionStatus`, `TokenUsage` |
| `health` | Health aggregation | `RuntimeHealthAggregator`, `HealthCheckResult`, `HealthStatus` |
| `execution` | Orchestration | `RuntimeCoordinator`, `ExecutionRequest`, `ExecutionResult` |

## Design Principles

- **Pure abstractions**: No provider SDKs, HTTP clients, or API keys
- **Immutable models**: All value objects are frozen dataclasses
- **Policy-driven**: Every behavior is configurable via immutable policy objects
- **No infrastructure deps**: No Redis, Temporal, or external services

## Usage

```python
from app.providers.runtime.execution.runtime_coordinator import (
    RuntimeCoordinator, ExecutionRequest
)

coordinator = RuntimeCoordinator(policy=ExecutionPolicy(...))
result = await coordinator.execute(
    ExecutionRequest(provider_name="openai", model_id="gpt-4"),
    handler=my_provider_call,
)
```
