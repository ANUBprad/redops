# Evaluation Domain Layer

Pure business logic for the Evaluation Engine. No infrastructure dependencies.

## Structure

```
evaluation/
├── domain/
│   ├── entities/          # AggregateRoot and Entity implementations
│   │   ├── EvaluationRun  # Aggregate root managing run lifecycle
│   │   ├── EvaluationItem # Entity for per-dataset-row processing
│   │   ├── ItemResult     # Immutable pipeline output for one item
│   │   ├── AggregatedMetrics # Computed aggregate scores
│   │   └── RunCheckpoint  # Serialized resume state
│   ├── value_objects/     # Immutable value objects
│   │   ├── EvaluationConfiguration # Complete eval config
│   │   ├── EvaluationProfile      # Provider/model profile
│   │   ├── DatasetReference       # Dataset reference
│   │   ├── ExecutionBudget        # Cost/time/token limits
│   │   ├── ExecutionLimits        # Concurrency limits
│   │   ├── ExecutionPolicy        # Failure handling policy
│   │   ├── EvaluationMetadata     # Project/author metadata
│   │   └── FailureSummary         # Aggregated failure info
│   ├── events/            # Typed domain events
│   │   ├── EvaluationCreated/Queued/Started/...
│   │   ├── ItemStarted/Completed/Failed/...
│   │   └── MetricComputed/Failed/Aggregated/...
│   ├── enums/             # Domain enumerations
│   │   ├── RunStatus      # Run lifecycle states
│   │   ├── ItemStatus     # Item processing states
│   │   ├── EvaluationType # Single/Dataset/Regression/...
│   │   ├── FailureReason  # Categorized failure types
│   │   ├── CancellationReason # Why a run was cancelled
│   │   └── Priority       # Execution priority
│   ├── state_machine/     # Run lifecycle state machine
│   │   └── RunStateMachine # Transition validation + guards
│   ├── factories/         # Valid object creation
│   │   ├── EvaluationConfigurationFactory
│   │   ├── EvaluationRunFactory
│   │   ├── EvaluationItemFactory
│   │   ├── RunCheckpointFactory
│   │   └── AggregatedMetricsFactory
│   ├── validators/        # Invariant enforcement
│   │   ├── EvaluationValidator
│   │   └── StateTransitionValidator
│   ├── services/          # Pure domain services
│   │   ├── TransitionValidator
│   │   ├── FailureThresholdPolicy
│   │   ├── BudgetPolicy
│   │   └── ExecutionPolicyResolver
│   └── contracts/         # Abstract interfaces
│       ├── RunRepository
│       ├── ItemRepository
│       ├── CheckpointRepository
│       └── EventPublisher
```

## Key Design Decisions

- **No infrastructure dependencies**: No SQLAlchemy, FastAPI, Redis, Temporal, or provider SDKs
- **Kernel abstractions**: Uses `AggregateRoot`, `Entity`, `DomainEvent`, `UUIDv7` from the Platform Kernel
- **Immutable value objects**: All value objects are frozen dataclasses
- **State machine**: Validates all transitions against the approved lifecycle diagram
- **Factories**: Enforce invariants at creation time
- **Typed errors**: All domain errors extend `DomainError` from the Kernel
- **Events are raised, not published**: `AggregateRoot.raise_event()` records events; infrastructure publishes them

## State Machine

```
CREATED → QUEUED → STARTING → RUNNING → PAUSED
                                    ↓
                               CANCELLING → COMPLETED
                                    ↓
                               CANCELLED
                                    ↓
                               FAILED
                                    ↓
                               TIMEDOUT
```

## Usage

```python
from app.evaluation.domain.factories.evaluation_factories import (
    EvaluationConfigurationFactory,
    EvaluationRunFactory,
)

# Create configuration
config = EvaluationConfigurationFactory.create(
    name="GPT-4 Accuracy Test",
    eval_type=EvaluationType.DATASET,
    profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
    dataset=DatasetReference(dataset_id="ds-001", row_count=100),
    metrics=("accuracy", "relevance"),
)

# Create and queue a run
run = EvaluationRunFactory.create_queued(config=config, profile=config.profile)

# Start execution
run.start(total_items=100)

# Pause and resume
run.pause()
run.resume()

# Complete
run.complete()

# Collect domain events
events = run.collect_events()
```
