# Evaluation Engine Architecture

> **Status:** Architecture Design  
> **Author:** Principal AI Systems Architect  
> **Last Updated:** 2026-07-25  
> **Reviewers:** Senior Backend Engineers, AI Platform Engineers

---

## 1. Executive Summary

The Evaluation Engine is the orchestration core of RedOps Eval. It transforms evaluation definitions into completed results through a deterministic, recoverable, and observable pipeline. The engine never knows which AI provider it calls, which metrics it computes, or where results are stored. Every concern is abstracted behind a contract.

This document defines the architecture, component boundaries, domain model, and integration contracts for the Evaluation Engine.

---

## 2. Architectural Principles

| Principle | Meaning |
|---|---|
| **Provider Agnosticism** | The engine interacts only with `ProviderRegistry` and `ChatProvider`/`EmbeddingProvider` contracts. It never imports OpenAI, Anthropic, or any SDK. |
| **Metric Extensibility** | Metrics are plugins discovered at runtime. The engine defines the execution contract; metrics define the computation. |
| **Deterministic Recovery** | Any interrupted run can be resumed from the last checkpoint without re-executing completed work. |
| **Immutable Inputs** | Evaluation definitions, dataset items, and configuration are immutable value objects. State mutations occur only on the Evaluation Run entity. |
| **Event Sourcing** | Every state transition produces a domain event. The current state is reconstructable from the event log. |
| **Temporal Orchestration** | Long-running evaluations are Temporal workflows. The engine defines activities; Temporal manages durability, retries, and timeouts. |

---

## 3. Bounded Context Boundary

```
┌─────────────────────────────────────────────────────────────────┐
│                     EVALUATION ENGINE                           │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │  Domain   │  │Pipeline  │  │Metrics   │  │ Orchestration│   │
│  │  Model    │  │Stages    │  │Framework │  │ (Temporal)   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
│       │              │              │               │            │
│  ┌────┴──────────────┴──────────────┴───────────────┴───────┐   │
│  │                   Engine Contracts                        │   │
│  └────┬──────────────┬──────────────┬───────────────┬───────┘   │
└───────┼──────────────┼──────────────┼───────────────┼───────────┘
        │              │              │               │
   ┌────▼─────┐  ┌─────▼────┐  ┌─────▼─────┐  ┌─────▼──────┐
   │ Provider  │  │ Plugin   │  │ Event Bus │  │ Repository │
   │ Registry  │  │ Registry │  │ (Redis)   │  │ (SQLAlchemy│
   └──────────┘  └──────────┘  └───────────┘  └────────────┘
```

**What lives inside the Evaluation Engine:**

- Domain model (Evaluation, EvaluationRun, EvaluationItem, EvaluationResult)
- Pipeline stage definitions and orchestration
- Metric computation dispatch (not computation itself)
- State machine and transition logic
- Event emission for every state change
- Checkpointing and recovery logic

**What lives outside (injected via contracts):**

- Provider invocation (Provider Registry)
- Metric computation (Plugin Registry)
- Event publishing (Event Bus / Redis Streams)
- Persistence (Repository pattern)
- Workflow durability (Temporal)

---

## 4. Core Domain Model

### 4.1 Entity Hierarchy

```
Experiment (aggregate root)
  └── Evaluation (value object — the "what to run")
        └── EvaluationRun (entity — the "running instance")
              ├── EvaluationItem (entity — one dataset row)
              │     └── ItemResult (value object)
              └── RunMetrics (value object — aggregated)
```

### 4.2 Evaluation (Definition)

An **Evaluation** is an immutable definition describing what to execute. It is created once and never mutated.

```
Evaluation {
    evaluation_id:       UUIDv7
    experiment_id:       UUIDv7
    name:                str
    description:         str
    evaluation_type:     EvaluationType        # SINGLE | DATASET | REGRESSION | SAFETY | RAG | COMPARISON
    profile:             EvaluationProfile      # model, provider, parameters
    dataset_reference:   DatasetReference       # pointer to dataset (not the data itself)
    metric_configs:      list[MetricConfig]     # which metrics to compute
    configuration:       EvaluationConfig       # concurrency, timeouts, retry policy
    created_at:          datetime
    created_by:          UUIDv7
}
```

### 4.3 EvaluationProfile

Describes *how* to invoke the provider.

```
EvaluationProfile {
    provider_name:       str                    # "openai", "anthropic", etc.
    model_id:            str                    # "gpt-4o", "claude-sonnet-4-20250514", etc.
    system_prompt:       str | None
    temperature:         float | None
    max_tokens:          int | None
    stop_sequences:      list[str] | None
    tools:               list[ToolDefinition] | None
    response_format:     ResponseFormat | None
    timeout_seconds:     float
    metadata:            dict[str, Any]
}
```

### 4.4 EvaluationRun (Execution Instance)

An **EvaluationRun** is the mutable entity tracking a single execution of an Evaluation. It is the stateful core of the engine.

```
EvaluationRun {
    run_id:              UUIDv7
    evaluation_id:       UUIDv7
    status:              RunStatus              # state machine (see STATE_MACHINE.md)
    started_at:          datetime | None
    completed_at:        datetime | None
    checkpoint:          RunCheckpoint           # last persisted state
    item_results:        list[ItemResult]        # completed item results
    aggregated_metrics:  AggregatedMetrics | None
    token_usage:         TokenUsage              # accumulated across all items
    cost_usd:            float                   # accumulated cost
    error:               RunError | None         # terminal error if failed
    retry_count:         int
    created_at:          datetime
    updated_at:          datetime
}
```

### 4.5 EvaluationItem (Dataset Row)

One row from the dataset, processed independently.

```
EvaluationItem {
    item_id:             UUIDv7
    run_id:              UUIDv7
    index:               int                     # position in dataset
    status:              ItemStatus              # PENDING | RUNNING | COMPLETED | FAILED | SKIPPED
    input:               dict[str, Any]          # dataset row (template variables)
    rendered_prompt:     str | None              # after template rendering
    provider_response:   ChatResponse | None     # raw provider output
    item_metrics:        dict[str, MetricResult] # per-metric results
    error:               ItemError | None
    started_at:          datetime | None
    completed_at:        datetime | None
    retry_count:         int
    duration_ms:         float | None
}
```

### 4.6 EvaluationType

Determines the execution strategy, not the pipeline.

| Type | Description | Dataset Required | Multi-Model |
|---|---|---|---|
| `SINGLE` | One prompt, one model | No | No |
| `DATASET` | Many rows, one model | Yes | No |
| `REGRESSION` | Compare against baseline | Yes (with baselines) | No |
| `SAFETY` | Adversarial / red-team prompts | Yes | No |
| `RAG` | Retrieval-augmented generation | Yes (with contexts) | No |
| `COMPARISON` | Same dataset, multiple models | Yes | Yes |

### 4.7 DatasetReference

A pointer to a dataset, not the data itself. The engine fetches data at execution time.

```
DatasetReference {
    dataset_id:          UUIDv7
    version:             str | None              # pin to specific version
    filter:              DatasetFilter | None    # optional row filter
    limit:               int | None              # max rows to process
}
```

---

## 5. Component Decomposition

### 5.1 Engine Core

Responsible for:
- Translating an Evaluation definition into an executable plan
- Managing the EvaluationRun lifecycle
- Coordinating pipeline execution
- Emitting domain events at every state transition

The Engine Core never executes work directly. It delegates to:

### 5.2 Pipeline Executor

Processes each EvaluationItem through a sequence of stages:

```
TemplateRendering → ProviderInvocation → ResponseParsing → MetricComputation → ResultAggregation
```

See `EXECUTION_PIPELINE.md` for full stage definitions.

### 5.3 Metric Dispatcher

Discovers and invokes metric plugins. The engine calls:

```
metric_plugin.compute(request: MetricRequest) -> MetricResult
```

The engine has zero knowledge of what "accuracy", "hallucination rate", or "toxicity" mean. Metrics are plugins registered in the Plugin Registry under `metric_type`.

### 5.4 Checkpoint Manager

Persists run state at configurable intervals. Enables resume-from-checkpoint on crash or failure. See `CHECKPOINTING.md`.

### 5.5 Event Emitter

Publishes domain events to the Event Bus (Redis Streams) at every state transition. Events are the primary integration point for external systems (dashboards, webhooks, alerts).

---

## 6. Integration Contracts

### 6.1 Engine → Provider Registry

```python
# The engine resolves providers by name, never by implementation
provider = provider_registry.resolve(profile.provider_name)

# The engine calls through the ChatProvider contract
response: ChatResponse = await provider.chat(
    messages=messages,
    model=profile.model_id,
    options=chat_options,
)
```

**Contract boundary:** The engine imports `ProviderRegistry` and `ChatProvider`. It never imports `OpenAIProvider`, `AnthropicProvider`, or any concrete class.

### 6.2 Engine → Plugin Registry (Metrics)

```python
# Metrics are discovered by plugin_type="metric"
metric_plugins = plugin_registry.get_all(plugin_type="metric")

# Each metric is invoked through a uniform contract
result: MetricResult = await metric_plugin.compute(
    MetricRequest(
        prediction=response.content,
        reference=expected_output,
        context=item.input,
    )
)
```

**Contract boundary:** The engine imports `PluginRegistry` and `MetricPlugin`. It never imports `AccuracyPlugin`, `HallucinationPlugin`, or any concrete class.

### 6.3 Engine → Event Bus

```python
# Every state transition produces an event
await event_bus.publish(
    EvaluationStarted(
        run_id=run.run_id,
        evaluation_id=run.evaluation_id,
        item_count=dataset.size,
    )
)
```

**Contract boundary:** The engine imports `EventPublisher`. It never imports `RedisStreamsEventBus`.

### 6.4 Engine → Repository

```python
# Persistence through repository pattern
await run_repository.save(run)
await item_repository.save(item)
await result_repository.save(result)
```

**Contract boundary:** The engine imports `Repository[EvaluationRun]`. It never imports SQLAlchemy models or database schemas.

---

## 7. Execution Flow Overview

```
User creates Evaluation
        │
        ▼
┌───────────────────┐
│  EvaluationCreated │──── event ────▶ Event Bus
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  EvaluationQueued  │──── event ────▶ Event Bus
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Temporal Workflow │  (EvaluationRunWorkflow)
│  starts            │
└────────┬──────────┘
         │
         ├──────────────────────────────────────┐
         │                                      │
         ▼                                      ▼
┌─────────────────┐                  ┌─────────────────┐
│  For each item   │                  │  Checkpoint      │
│  in dataset      │◄──── resume ────│  Manager         │
│                  │                  └─────────────────┘
│  ┌────────────┐  │
│  │  Render     │  │
│  │  Template   │  │
│  └─────┬──────┘  │
│        ▼          │
│  ┌────────────┐  │
│  │  Invoke     │  │
│  │  Provider   │  │──── event ────▶ ProviderInvoked
│  └─────┬──────┘  │
│        ▼          │
│  ┌────────────┐  │
│  │  Parse      │  │──── event ────▶ ResponseReceived
│  │  Response   │  │
│  └─────┬──────┘  │
│        ▼          │
│  ┌────────────┐  │
│  │  Compute    │  │──── event ────▶ MetricCompleted
│  │  Metrics    │  │
│  └─────┬──────┘  │
│        ▼          │
│  ┌────────────┐  │
│  │  Persist    │  │
│  │  Result     │  │
│  └─────┬──────┘  │
│        ▼          │
│  Checkpoint       │
└────────┬─────────┘
         │
         ▼
┌───────────────────┐
│  Aggregate Metrics │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  EvaluationCompleted│──── event ────▶ Event Bus
└───────────────────┘
```

---

## 8. Extensibility Points

| Extension Point | Mechanism | Example |
|---|---|---|
| New metric | Implement `MetricPlugin`, register with `plugin_type="metric"` | Add BLEU score, toxicity detector |
| New evaluation type | Add enum value + execution strategy | Agent evaluation, multimodal evaluation |
| New pipeline stage | Implement `PipelineStage` protocol, insert into stage chain | Output parsing, guardrail checking |
| New provider | Implement `ChatProvider` + `BaseProvider`, register with `provider_registry` | Add Groq, Together AI |
| New dataset format | Implement `DatasetLoader` plugin | CSV, JSONL, Parquet |
| New event consumer | Subscribe to event types via `EventBus.subscribe()` | Webhook notifier, Slack alert |

---

## 9. Non-Functional Requirements

| Requirement | Target | Mechanism |
|---|---|---|
| Durability | Zero data loss on crash | Temporal workflow persistence + checkpointing |
| Throughput | 10,000 items/hour/model | Parallel execution with concurrency limits |
| Latency (single item) | < provider latency + 100ms overhead | Minimal pipeline overhead |
| Recovery time | < 30 seconds from checkpoint | Checkpoint frequency = 50 items |
| Cost tracking | Per-item accuracy | Accumulated TokenUsage + CostCalculator |
| Observability | Full trace per run | Domain events + structured logging |
| Extensibility | 5-year horizon | Plugin system + protocol-based contracts |

---

## 10. Document Map

| Document | Purpose |
|---|---|
| [EXECUTION_PIPELINE.md](EXECUTION_PIPELINE.md) | Pipeline stage definitions and data flow |
| [STATE_MACHINE.md](STATE_MACHINE.md) | Run lifecycle states and valid transitions |
| [EVENT_FLOW.md](EVENT_FLOW.md) | Domain events catalog with publisher/consumer mapping |
| [FAILURE_HANDLING.md](FAILURE_HANDLING.md) | Failure modes and recovery strategies |
| [CHECKPOINTING.md](CHECKPOINTING.md) | Checkpoint contents, frequency, and recovery |
| [EXECUTION_MODEL.md](EXECUTION_MODEL.md) | Temporal workflow and activity decomposition |
| [RETRY_POLICY.md](RETRY_POLICY.md) | Retry semantics, backoff, and idempotency |
| [CANCELLATION_MODEL.md](CANCELLATION_MODEL.md) | Cancellation propagation and cleanup |
| [PARALLEL_EXECUTION.md](PARALLEL_EXECUTION.md) | Concurrency, partitioning, and backpressure |
| [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) | Architectural decision records with rationale |
