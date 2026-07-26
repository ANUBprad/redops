# Design Decisions

> **Status:** Architecture Design  
> **Supersedes:** All other evaluation engine architecture documents

---

## 1. Purpose

This document captures architectural decisions, rationale, and tradeoffs for the Evaluation Engine. It serves as a reference for future contributors to understand why the system is designed the way it is.

---

## 2. Decision Log

### AD-001: Temporal for Workflow Orchestration

**Status:** Accepted  
**Context:** The evaluation engine needs durable execution, automatic retries, and signal handling for pause/resume/cancel.

**Options Considered:**
1. **Temporal** — Durable workflow execution, built-in retries, signals, versioning
2. **Celery** — Task queue with retries, but no durable execution or workflow versioning
3. **Redis Queue** — Simple task queue, no durability, manual retry logic
4. **Custom orchestrator** — Full control, but reimplements Temporal's features

**Decision:** Use Temporal.

**Rationale:**
- Durability: Workflow state survives worker crashes without manual checkpointing
- Retries: Activity retry policies with exponential backoff built-in
- Signals: Pause/resume/cancel via Temporal signals
- Versioning: Safe workflow deployments with version checks
- Observability: Temporal UI shows workflow state and history

**Tradeoffs:**
- Adds operational complexity (worker management, namespace configuration)
- Requires Temporal cluster deployment (or Temporal Cloud)
- Learning curve for developers unfamiliar with Temporal

**Consequences:**
- Evaluation engine is durable and reliable
- Operations team must manage Temporal infrastructure
- Worker deployments require versioning discipline

---

### AD-002: One Workflow Per Evaluation Run

**Status:** Accepted  
**Context:** How to map evaluation runs to Temporal workflows.

**Options Considered:**
1. **One workflow per run** — Each run is an independent workflow
2. **One workflow per evaluation** — All runs of an evaluation share a workflow
3. **One workflow per batch** — Multiple runs batched into one workflow

**Decision:** One workflow per run.

**Rationale:**
- Natural isolation: Each run has its own state, retry policy, and timeout
- Simple cancellation: Cancel one run without affecting others
- Simple checkpointing: Each run checkpoints independently
- Temporal visibility: Each run is a separate workflow in the Temporal UI

**Tradeoffs:**
- More workflow instances (but Temporal handles this efficiently)
- Each workflow has overhead (but minimal for our scale)

**Consequences:**
- Clean run isolation
- Simple API mapping (run_id → workflow_id)
- Easy to reason about run lifecycle

---

### AD-003: Fixed Partitioning for Parallel Execution

**Status:** Accepted  
**Context:** How to partition datasets for parallel evaluation.

**Options Considered:**
1. **Fixed partitioning** — Dataset split into fixed chunks upfront
2. **Dynamic partitioning** — Work-stealing between partitions
3. **No partitioning** — Sequential execution only

**Decision:** Fixed partitioning for v1.

**Rationale:**
- Simple to implement and reason about
- Predictable resource usage
- Easy to checkpoint (each partition checkpoints independently)
- Good enough for most evaluation scenarios

**Tradeoffs:**
- May imbalance if items vary in complexity (but rare in practice)
- Cannot adapt to runtime conditions (but can be added later)

**Consequences:**
- Parallel execution reduces evaluation time by 3-5x
- Simple checkpointing and resume logic
- Future: Dynamic partitioning can be added if profiling shows imbalance

---

### AD-004: Checkpoint After Every N Items

**Status:** Accepted  
**Context:** How often to checkpoint evaluation progress.

**Options Considered:**
1. **Every item** — Maximum granularity, highest overhead
2. **Every N items** — Balanced (default: 50)
3. **Time-based** — Checkpoint every M seconds
4. **No checkpointing** — Risk losing all progress on failure

**Decision:** Checkpoint after every N items (default: 50).

**Rationale:**
- Balances overhead (checkpoint write time) with granularity (progress preservation)
- 50 items means at most 49 items of rework on failure
- Checkpoint write is fast (~100KB JSONB)
- Configurable per evaluation if needed

**Tradeoffs:**
- Losing up to N-1 items of progress on failure (acceptable)
- Checkpoint storage grows with dataset size (pruned after 30 days)

**Consequences:**
- Reasonable recovery time after failure
- Acceptable storage overhead
- Simple implementation

---

### AD-005: Provider Abstraction Layer

**Status:** Accepted  
**Context:** How to support multiple AI providers without coupling the engine to any specific provider.

**Options Considered:**
1. **Provider abstraction** — Interface-based, zero SDK dependencies
2. **Provider SDK integration** — Direct SDK usage per provider
3. **HTTP client per provider** — Custom HTTP clients

**Decision:** Provider abstraction layer.

**Rationale:**
- Zero provider SDK dependencies in the engine
- Easy to add new providers (implement interface)
- Easy to test (mock providers)
- Provider selection at runtime

**Tradeoffs:**
- Must maintain provider abstractions as providers evolve
- Cannot use provider-specific features without abstraction leakage
- More code than direct SDK usage

**Consequences:**
- Clean separation between engine and providers
- Easy to add new providers
- Testable without API keys

---

### AD-006: Event-Driven Architecture

**Status:** Accepted  
**Context:** How to communicate state changes and integrate with external systems.

**Options Considered:**
1. **Event-driven** — Domain events via Event Bus
2. **Polling** — External systems poll for state changes
3. **Webhooks** — Direct HTTP callbacks to external systems
4. **Mixed** — Events for internal, webhooks for external

**Decision:** Event-driven with webhook forwarding.

**Rationale:**
- Loose coupling between components
- Easy to add new consumers (subscribe to events)
- Natural audit trail (events are immutable)
- Webhook forwarding for external systems
- Real-time updates for dashboards

**Tradeoffs:**
- Event ordering requires care (UUIDv7 timestamp-based)
- Event versioning adds complexity
- Best-effort delivery (not exactly-once)

**Consequences:**
- Clean component boundaries
- Easy to extend with new integrations
- Natural observability via event streams

---

### AD-007: Item-Level Failure Isolation

**Status:** Accepted  
**Context:** How to handle failures of individual evaluation items.

**Options Considered:**
1. **Item isolation** — Each item fails independently
2. **Run failure** — Any item failure fails the entire run
3. **Configurable** — Let users choose per evaluation

**Decision:** Item-level isolation with configurable continuation policy.

**Rationale:**
- Most evaluation runs have hundreds of items
- Failing the entire run for one bad item wastes completed work
- Users can configure strict mode if needed
- Partial results are still valuable

**Tradeoffs:**
- More complex failure tracking
- Aggregated metrics may be skewed by failed items
- Users must check for partial results

**Consequences:**
- Robust to individual item failures
- Partial results are preserved
- Users can choose strict or lenient failure handling

---

### AD-008: Frozen Dataclasses for Domain Models

**Status:** Accepted  
**Context:** How to represent domain entities in the evaluation engine.

**Options Considered:**
1. **Frozen dataclasses** — Immutable, hashable, type-safe
2. **Pydantic models** — Validation, serialization, but mutable
3. **Named tuples** — Immutable, but no validation
4. **Regular classes** — Mutable, no validation

**Decision:** Frozen dataclasses for domain models.

**Rationale:**
- Immutability prevents accidental mutation
- Hashable enables use in sets and as dict keys
- Type-safe with full mypy support
- No Pydantic dependency (keep dependencies minimal)
- Fast instantiation (dataclass is faster than Pydantic)

**Tradeoffs:**
- No built-in validation (must add manually)
- No built-in serialization (must add manually)
- Cannot mutate (must create new instances)

**Consequences:**
- Clean, predictable domain models
- No accidental mutation bugs
- Fast execution

---

### AD-009: Google-Style Docstrings

**Status:** Accepted  
**Context:** How to document code in the evaluation engine.

**Options Considered:**
1. **Google-style** — Clean, readable, widely used
2. **NumPy-style** — More verbose, common in scientific computing
3. **Sphinx-style** — RST-based, verbose
4. **No docstrings** — Minimal documentation

**Decision:** Google-style docstrings.

**Rationale:**
- Clean and readable
- Widely adopted in Python ecosystem
- Good tooling support (sphinx, pydocstyle)
- Concise while being informative

**Tradeoffs:**
- Requires discipline to maintain
- Can become outdated if not maintained

**Consequences:**
- Consistent documentation style
- Easy to read and maintain
- Good tooling support

---

### AD-010: Ruff for Linting + mypy for Type Checking

**Status:** Accepted  
**Context:** How to enforce code quality in the evaluation engine.

**Options Considered:**
1. **Ruff + mypy** — Fast linting + strict type checking
2. **Flake8 + mypy** — Traditional linting + type checking
3. **Pylint + mypy** — Comprehensive linting + type checking
4. **No linting** — Relies on code review

**Decision:** Ruff for linting + mypy for type checking.

**Rationale:**
- Ruff is extremely fast (Rust-based)
- Ruff replaces flake8, isort, pyupgrade, and more
- mypy provides strict type checking
- Both are configurable via pyproject.toml
- CI/CD integration is straightforward

**Tradeoffs:**
- Ruff is newer (less mature than flake8)
- mypy strict mode can be noisy
- Configuration requires tuning

**Consequences:**
- Fast, reliable code quality enforcement
- Consistent code style across the codebase
- Type safety prevents runtime errors

---

## 3. Open Decisions

### OD-001: Streaming Response Handling

**Status:** Pending  
**Context:** How to handle streaming responses from providers for real-time token counting.

**Options:**
1. **Buffer full response** — Wait for complete response, then parse
2. **Stream to buffer** — Accumulate tokens in real-time
3. **Hybrid** — Stream for display, buffer for processing

**Tradeoffs:**
- Buffering is simpler but delays feedback
- Streaming is complex but enables real-time progress
- Hybrid combines both but adds complexity

**Recommendation:** Buffer for v1. Add streaming in v2.

---

### OD-002: Cost Alerting Thresholds

**Status:** Pending  
**Context:** When to alert users about evaluation cost.

**Options:**
1. **Fixed threshold** — Alert when cost exceeds $X
2. **Percentage-based** — Alert when cost exceeds X% of budget
3. **Predictive** — Alert when projected cost exceeds budget
4. **None** — No cost alerting

**Tradeoffs:**
- Fixed threshold is simple but not adaptive
- Percentage-based requires budget configuration
- Predictive is complex but proactive
- None is simplest but risks cost overruns

**Recommendation:** Percentage-based with optional fixed threshold.

---

## 4. Glossary

| Term | Definition |
|---|---|
| **Evaluation** | A named configuration for evaluating AI model outputs |
| **Evaluation Run** | A single execution of an evaluation |
| **Evaluation Item** | One data point being evaluated |
| **Metric** | A computation applied to an item result to produce a score |
| **Provider** | An AI model provider (e.g., OpenAI, Anthropic) |
| **Model** | A specific AI model (e.g., gpt-4, claude-3-opus) |
| **Checkpoint** | Saved state for resuming an interrupted run |
| **Partition** | A subset of items processed in parallel |
| **Pipeline** | The sequence of stages executed for each item |
| **Activity** | A Temporal activity (unit of work in a workflow) |
| **Workflow** | A Temporal workflow (orchestration of activities) |
