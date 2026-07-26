# Execution Pipeline Layer

Pure application-level abstractions that connect the Evaluation Domain
to future orchestration. Contains **zero infrastructure dependencies**
— no Temporal, no SQLAlchemy, no Redis, no Provider SDKs, no Metric
implementations.

## Structure

```
execution/
├── contracts/          # Abstract interfaces (Pipeline, Executor, Planner, Scheduler, Observer)
├── pipeline/           # Data structures (ExecutionPlan, ExecutionStep, ExecutionPipeline)
├── planner/            # Planner base class
├── stages/             # StageType enum and ExecutionStage abstract base
├── context/            # PipelineContext (immutable execution context)
├── strategies/         # Strategy interfaces and policy objects
├── results/            # Domain-level result types (StepResult, StageResult, ExecutionResult)
├── validators/         # Validation rules (plan, dependency graph, budget, concurrency)
├── builders/           # PipelineBuilder (EvaluationRun → ExecutionPlan → ExecutionPipeline)
├── events/             # Execution-level domain events
└── README.md
```

## Key Design Decisions

- **No infrastructure dependencies**: Zero imports from Temporal, SQLAlchemy, Redis, FastAPI, or provider SDKs
- **Immutable data structures**: ExecutionPlan, ExecutionStep, PipelineContext, and all results are frozen dataclasses
- **Domain-level results only**: All result types describe what happened without referencing infrastructure
- **Strategy interfaces only**: Strategies define the contract but contain no execution logic
- **Builder pattern**: PipelineBuilder validates invariants at construction time
- **Event-driven**: Execution lifecycle events are domain events, not infrastructure messages
- **Kernel abstractions**: Uses UUIDv7 and DomainError from the Platform Kernel

## Data Flow

```
EvaluationRun
    ↓
ExecutionPlanner.plan()  ───→  ExecutionPlan (immutable, versioned)
    ↓
PipelineBuilder.build()  ───→  ExecutionPipeline (stages + steps)
    ↓
PipelineExecutor.execute() ──→  ExecutionResult
    ↓
PipelineSummary.from_result() → PipelineSummary (API-facing)
```

## Contracts

| Contract | Purpose |
|---|---|
| `Pipeline` | Top-level lifecycle: run, pause, resume, cancel |
| `PipelineExecutor` | Orchestrates stage execution in order |
| `StageExecutor` | Validates, executes, and rolls back individual stages |
| `ExecutionPlanner` | Transforms EvaluationRun into ExecutionPlan |
| `ExecutionScheduler` | Decides step ordering and concurrency |
| `ExecutionObserver` | Fire-and-forget lifecycle observation |

## Validators

| Validator | Purpose |
|---|---|
| `PlanValidator` | Structural plan correctness |
| `DependencyGraphValidator` | Circular dependency detection, missing deps |
| `BudgetValidator` | Budget parameter invariants |
| `ConcurrencyValidator` | Concurrency and limits configuration checks |
| `StageOrderingValidator` | Canonical stage ordering enforcement |

## Strategies

| Strategy | Behaviour |
|---|---|
| `SequentialExecution` | One step at a time, in order |
| `ParallelExecution` | Concurrent up to limit, dependency-aware |
| `AdaptiveExecution` | Dynamically adjusts to performance |
| `BudgetAwareExecution` | Monitors budget during execution |
| `PriorityExecution` | Higher priority steps execute first |

## Usage

```python
from app.evaluation.execution.builders.builder import PipelineBuilder
from app.evaluation.execution.context.context import PipelineContext
from app.evaluation.execution.pipeline.plan import ExecutionPlan
from app.evaluation.execution.pipeline.pipeline import ExecutionPipeline

# Build from a run
pipeline = await builder.build(run)

# Execute via a PipelineExecutor
result = await executor.execute(pipeline, context)

# Create a summary for API responses
summary = PipelineSummary.from_execution_result(result)
```

## Future Infrastructure Integration

Concrete implementations of these contracts (Temporal workflows,
Provider executors, Metric dispatchers, Repository adapters)
can be injected without modifying any of these files.
