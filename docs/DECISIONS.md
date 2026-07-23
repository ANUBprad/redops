# RedOps Eval — Architecture Decision Record

This document records significant architectural decisions and the reasoning behind them.

---

## ADR-001: FastAPI as the API Framework

**Status:** Accepted

**Context:** We need a Python web framework that supports async I/O, automatic OpenAPI generation, and strong request/validation via type hints. The framework will handle many concurrent LLM provider calls.

**Decision:** Use FastAPI.

**Reasoning:**
- Native `async`/`await` support allows concurrent HTTP calls to LLM providers without thread pool overhead.
- Pydantic-based request/response validation eliminates a separate validation layer.
- Automatic OpenAPI spec generation enables auto-generated TypeScript client types for the frontend.
- WebSocket support is first-class, which we need for real-time evaluation progress streaming.
- Dependency injection system simplifies database session management and provider registry wiring.

**Alternatives considered:**
- **Flask + Flask-RESTx:** Synchronous by default. Requires async hacks or gunicorn with gevent workers. No native WebSocket support.
- **Django + DRF:** Heavy framework for an API-only backend. Django's ORM is synchronous, requiring separate async worker configurations.

**Consequences:** Smaller middleware ecosystem compared to Django. Acceptable tradeoff for an API-first service.

---

## ADR-002: PostgreSQL as the Primary Database

**Status:** Accepted

**Context:** We need a database that stores structured, interrelated data (projects, runs, metrics, users) with strong consistency guarantees and support for analytical queries.

**Decision:** Use PostgreSQL 16+.

**Reasoning:**
- Relational model is the natural fit for our entity relationships (foreign keys, cascading deletes, join queries).
- JSONB columns allow flexible storage of metric configurations and provider settings without sacrificing the ability to index into them.
- Window functions and CTEs enable efficient analytical queries (metric trend aggregation, percentile calculations) without a separate analytics store.
- Mature async driver support (`asyncpg`) pairs well with FastAPI.
- Declarative partitioning allows scaling `metric_results` and `audit_log` tables without schema changes.

**Alternatives considered:**
- **TimescaleDB:** Hyperfunction-focused time-series features are overkill for our write-once read-many workload. PostgreSQL + materialized views suffice.
- **MongoDB:** Schema flexibility is unnecessary — our entities have well-defined shapes. The lack of foreign key enforcement would require application-level integrity checks.
- **MySQL:** Weaker JSON support, inferior CTE/window function performance.

**Consequences:** Vertical scaling for writes is limited. If ingestion volume exceeds 10M metric rows/month, we will shard by project_id or migrate analytical queries to ClickHouse.

---

## ADR-003: Provider Abstraction via Adapter Pattern

**Status:** Accepted

**Context:** RedOps Eval must support multiple LLM providers (OpenAI, Anthropic, Gemini, Ollama, Groq, OpenRouter) with different APIs, authentication methods, and response schemas.

**Decision:** Define a `BaseProviderAdapter` abstract class that all provider adapters implement. The domain core never directly imports a provider SDK.

**Reasoning:**
- **Isolation:** Provider-specific SDKs, authentication, and error handling are contained within adapter classes.
- **Testability:** Adapters can be individually unit-tested with mocked HTTP responses.
- **Extensibility:** Adding a new provider requires only a new adapter class and a registry entry — no changes to the evaluation pipeline.
- **Cost tracking:** Adapters normalize token counts and pricing into a common schema, enabling accurate cost comparison across providers.

**Pattern:**
```python
class BaseProviderAdapter(ABC):
    @abstractmethod
    async def generate(self, prompt: str, config: ProviderConfig) -> ProviderResponse: ...
    @abstractmethod
    async def generate_stream(self, prompt: str, config: ProviderConfig) -> AsyncIterator[ProviderChunk]: ...
    @abstractmethod
    def metadata(self) -> ProviderMetadata: ...
```

**Alternatives considered:**
- **Direct SDK calls in service layer:** Would couple the evaluation pipeline to every provider SDK. Adding a new provider would require changes across multiple service files.
- **LangChain as universal interface:** LangChain's `BaseChatModel` provides a unified interface, but it ties us to LangChain's evolving API and introduces a heavy dependency. We use LangChain only within specific adapters (Ollama, Groq) where it provides genuine value.

**Consequences:** Slight overhead for adapters that must transform provider-specific response schemas into the common `ProviderResponse`. Negligible in practice compared to network latency.

---

## ADR-004: Modular Metrics with Adapter Wrapper

**Status:** Accepted

**Context:** The platform must support many evaluation metrics with different computation methods (LLM-based, heuristic, direct measurement). The metrics set will grow over time, potentially with community-contributed metrics.

**Decision:** Define a `BaseMetric` interface. Each metric is a standalone class. DeepEval metrics are wrapped behind this interface.

**Reasoning:**
- **Replaceability:** If DeepEval is deprecated or a better library emerges, only the wrappers change — the metric interface and all consuming code remain unchanged.
- **Testability:** Metrics can be unit-tested with known inputs and expected outputs.
- **Composability:** A composite metric can aggregate sub-metrics without special-casing.
- **Plugin support:** The interface enables community-contributed metrics as plugins (importable via Python entry points).

**Alternatives considered:**
- **Direct DeepEval calls in evaluation pipeline:** Tight coupling. Changing metric libraries would require rewriting the evaluation pipeline.
- **One monolithic metric calculator class:** Violates Open/Closed principle. Every new metric requires changing the class.

**Consequences:** Slight indirection overhead. Every DeepEval metric needs a thin wrapper (~20 lines).

---

## ADR-005: Async-First Architecture with Durable Execution

**Status:** Accepted (Revised)

**Context:** The application is I/O-bound — database queries, LLM provider HTTP calls, Redis pub/sub, and file uploads all benefit from non-blocking I/O. Additionally, evaluation runs must survive process restarts and support complex failure recovery.

**Decision:** Use async Python throughout the API layer and domain service layer. Temporal handles all durable, long-running workflows. Temporal Activities execute in separate worker processes (synchronous or async as appropriate).

**Reasoning:**
- **LLM provider calls** are HTTP requests with 1–60 second response times. Async allows a single process to handle hundreds of concurrent in-flight requests.
- **WebSocket progress streaming** requires maintaining persistent connections. Async I/O handles this efficiently.
- **Database access** via `asyncpg` (driven by SQLAlchemy async) avoids blocking the event loop during queries.
- **Temporal** provides durable execution — workflows survive process crashes, server restarts, and network partitions. This is impossible to achieve reliably with Celery or in-process task queues.
- Temporal Activities can be either sync or async; CPU-bound metric computation runs in sync activities on separate worker threads, preventing starvation of async I/O.

**Alternatives considered:**
- **Synchronous Python with thread pool:** Thread safety issues, higher memory overhead per connection.
- **Full async with CPU-bound tasks in-process:** A blocking metric computation would stall the event loop.
- **Celery:** Lack of durable workflow state. Failed tasks must be manually retried. No built-in workflow state machine. Requires application code to track multi-step workflow progress.

**Consequences:** Temporal adds operational complexity (requires Temporal Server + its own database). Docker Compose makes this trivial for development. The benefits (durable execution, automatic retries, event history, built-in state management) justify the operational cost.

---

## ADR-006: Monorepo Structure

**Status:** Accepted

**Context:** The project has a Python backend and a TypeScript frontend. CI/CD, issue tracking, and releases must be coordinated.

**Decision:** Use a single monorepo with `backend/` and `frontend/` directories.

**Reasoning:**
- **Atomic changes:** A frontend change that requires a backend API change can be made in a single PR.
- **Shared CI/CD:** One CI pipeline runs all checks. Release tagging covers both packages.
- **Lower overhead:** No cross-repo dependency management, no separate pull requests for coordinated changes.
- **Open-source onboarding:** Contributors find everything in one place.

**Alternatives considered:**
- **Separate repos:** Required coordinated releases, cross-repo CI triggers, and more complex versioning.
- **Monorepo with separate packages:** Over-engineered for a two-package project.

**Consequences:** CI time is longer (must run both backend and frontend checks). Parallel job execution in GitHub Actions mitigates this. As the project grows, we may split into separate packages within the monorepo.

---

## ADR-007: React with TypeScript for the Frontend

**Status:** Accepted

**Context:** We need a rich, interactive SPA for dashboards, data tables, and real-time updates.

**Decision:** Use React 18+ with TypeScript, Vite, Tailwind CSS, and shadcn/ui.

**Reasoning:**
- **Ecosystem maturity:** React has the largest component library ecosystem (TanStack Query, Recharts, React Router, etc.).
- **TypeScript:** Auto-generated types from OpenAPI spec enable end-to-end type safety.
- **Vite:** Fast HMR and optimized builds.
- **Tailwind + shadcn/ui:** Full control over UI components without fighting a design system. shadcn/ui's copy-paste model means components are owned in our codebase.

**Alternatives considered:**
- **Next.js:** SSR/SSG adds complexity for an authenticated SPA. No SEO benefit because the app requires authentication.
- **Vue 3:** Smaller ecosystem for charting and data table libraries.
- **Svelte:** Smaller hiring pool and ecosystem.

**Consequences:** Larger initial bundle size compared to lighter frameworks. Mitigated by code splitting and lazy loading via Vite.

---

## ADR-008: Temporal for Workflow Orchestration (Replaces Celery)

**Status:** Superseded by ADR-014.

**Rationale:** See ADR-014 for the replacement decision. The original ADR-008 recommended Celery; this entry documents that the decision was revisited and reversed during the architecture review.

**Reason for reversal:** Celery is a task queue, not a workflow orchestrator. It lacks:
- Durable workflow state (no built-in state machine for multi-step processes).
- Event history (cannot replay or debug past workflow executions).
- Cancellation scopes (cannot cleanly cancel in-flight work).
- Saga pattern support (no automatic rollback on failure).
- Deterministic replay (for testing and recovery).

Temporal provides all of these, making it the correct choice for a production-grade evaluation platform that must handle thousands of runs per day reliably.

---

## ADR-014: Temporal for Durable Workflow Orchestration

**Status:** Accepted

**Context:** Evaluation runs are multi-step processes (resolve config → fan-out prompts → compute metrics → aggregate → trigger side effects). They may take hours, involve hundreds of parallel LLM calls, and must survive process restarts. Teams running thousands of evaluations per day cannot tolerate silent failures or state loss.

**Decision:** Use Temporal as the workflow orchestration engine for all long-running operations. Temporal replaces Celery entirely.

**Reasoning:**
- **Durable execution:** Workflow state persists in Temporal Server's database. Worker crashes do not lose progress. Workflows resume from the last completed Activity.
- **Event history:** Every state transition is recorded. Enables debugging, replay, and audit.
- **Parallel fan-out:** Execute hundreds of provider calls concurrently with automatic result collection. Temporal handles the async/sync boundary.
- **Cancellation scopes:** Cleanly cancel in-flight evaluation runs. Providers receive cancellation signals, partial results are preserved.
- **Saga pattern:** Rollback Activities on failure (e.g., mark run as failed, publish error event).
- **Cron workflows:** Built-in scheduled execution (replaces Celery Beat).
- **Python SDK:** First-class Python support with type hints and async compatibility.
- **Self-hostable:** Temporal Server runs on-premise with its own PostgreSQL database. No external cloud dependency.

**Alternatives considered:**
- **Celery:** Task queue, not workflow engine. Requires manual state management. No event history. As evaluated in ADR-008, it is insufficient for our requirements.
- **Hatchet:** Newer, Python-first workflow engine. Smaller community, less battle-tested in production at scale.
- **Arq:** Simple Redis-based queue. No workflow state management. Suitable for simple jobs, not multi-step workflows.
- **Inngest:** Serverless-focused. Not self-hostable. Not suitable for on-premise deployment.

**Consequences:** Temporal adds infrastructure complexity (Temporal Server + its own PostgreSQL database). The Temporal dev server (single binary) mitigates this for development. Production deployments need a properly configured Temporal cluster, but this is a one-time operational investment with significant reliability returns.

---

## ADR-015: Event Bus for Service Decoupling

**Status:** Accepted

**Context:** Domain services need to communicate asynchronously without direct coupling. Evaluation Engine should not know about webhooks, audit logging, or email notifications. Adding new side effects should not require changing existing services.

**Decision:** Introduce an Event Bus with Redis Streams as the production implementation. All inter-context communication happens through domain events.

**Reasoning:**
- **Decoupling:** Evaluation Engine publishes `EvaluationCompleted` once. Webhook delivery, audit logging, report refresh, and threshold notification each subscribe independently.
- **Extensibility:** Adding a new subscriber (e.g., Slack notification) requires no changes to existing publishers. Register a new handler for an existing event.
- **Resilience:** Redis Streams provide durable message storage with consumer groups. A subscriber crash does not lose events; other consumers in the group pick them up.
- **Observability:** The Event Log table stores all published events for debugging, replay, and distributed tracing via correlation IDs.
- **Testing:** The in-memory event bus implementation allows tests to assert that specific events were published without spinning up Redis.

**Alternatives considered:**
- **Direct service calls:** Tight coupling. Adding a side effect requires changing the calling service.
- **Message broker without stream semantics (RabbitMQ direct exchanges):** Lacks consumer groups for load-balanced processing. No built-in message replay.
- **Apache Kafka:** Over-engineered for our volume. Kafka's log compaction and multi-consumer group features are unnecessary. Redis Streams provide sufficient durability and ordering guarantees.

**Consequences:** All inter-context communication is asynchronous. Request-response patterns (e.g., API → database) remain synchronous. Eventual consistency is acceptable for all event-driven side effects (webhooks, notifications, report refresh). Redis is already required for the rate limiter and WebSocket pub/sub, so no new infrastructure dependency is introduced.

---

## ADR-016: Plugin Architecture for Metrics

**Status:** Accepted

**Context:** The platform must support a growing number of evaluation metrics, including community-contributed ones. Metrics should be independently versioned, discoverable, and installable without modifying the core codebase.

**Decision:** Implement metrics as plugins discovered via Python entry points (`importlib.metadata.entry_points`). Each metric is a self-contained Python package implementing `BaseMetric`.

**Reasoning:**
- **Discoverability:** The MetricRegistry scans entry points at startup. No manual registration needed.
- **Versioning:** Each metric declares its own semver version. MetricResults reference the exact MetricDefinition version used, enabling accurate reproducibility.
- **Isolation:** A buggy metric plugin cannot crash the entire evaluation pipeline. Error handling wraps each metric computation.
- **Distribution:** Community metrics can be distributed as PyPI packages with a single entry point declaration.
- **Third-party support:** Enterprise teams can write proprietary metrics without forking the codebase.

**Alternatives considered:**
- **Monolithic metrics module:** Every metric baked into the codebase. Community contributions require pull requests and maintainer review. Versioning is implicit (git commit), not explicit.
- **YAML/JSON metric definitions without code:** Suitable for simple heuristics but insufficient for LLM-based evaluation that requires custom logic.

**Consequences:** Plugin discovery adds ~50ms to startup time. Each plugin is a separate dependency that must be installed. The plugin API must be stable and well-documented to support the community ecosystem.

---

## ADR-017: Evaluator Abstraction Layer

**Status:** Accepted

**Context:** Metrics must not depend directly on DeepEval, because:
- DeepEval may be deprecated or change its API.
- Alternative evaluation libraries exist (RAGAS, Azure AI Evaluation, internal tools).
- Different metrics may need different evaluation backends.

**Decision:** Introduce `BaseEvaluatorAdapter` as the interface between metrics and evaluation libraries. The EvaluatorRegistry routes metric computation requests to the correct adapter.

**Reasoning:**
- **Swappable infrastructure:** DeepEval can be replaced with another library by writing a new adapter. All existing metrics continue to work.
- **Multi-library support:** Some metrics use DeepEval (hallucination), others use RAGAS (context recall), others are heuristic (latency). The registry dispatches each metric to the correct adapter.
- **Testing:** Evaluator adapters can be individually unit-tested with mocked library calls. Metrics can be tested with a mock evaluator.
- **Future-proofing:** When LangChain releases a new evaluation module or Azure AI Evaluation SDK matures, an adapter can be written without changing the metric interface.

**Flow:**
```
Metric.compute(inputs) → calls EvaluatorRegistry.evaluate(metric, inputs)
EvaluatorRegistry → looks up metric.metadata.evaluator_type
                  → routes to DeepEvalAdapter / RAGASAdapter / CustomAdapter
Adapter → calls underlying library → returns normalized MetricOutput
```

**Alternatives considered:**
- **Direct DeepEval calls in every metric:** Tight coupling. Changing libraries requires rewriting every metric.
- **Library-agnostic metric interface with runtime import switching:** Import-time dependency resolution is fragile. The adapter pattern provides cleaner separation.

**Consequences:** Slight indirection overhead per metric computation (microseconds). Adapters must be maintained alongside the libraries they wrap. The adapter interface must be general enough to accommodate different evaluation paradigms (LLM-based, heuristic, deterministic).

---

## ADR-018: Provider-Model Separation

**Status:** Accepted

**Context:** The initial design mixed providers and models in `provider_settings`. This prevents accurate cost tracking, capability-based routing, and graceful model deprecation.

**Decision:** Separate providers (OpenAI, Anthropic) from models (gpt-4o, claude-3-opus). Models are first-class entities in the database with capabilities, pricing, rate limits, and context window.

**Reasoning:**
- **Accurate cost tracking:** Pricing changes per model, not per provider. The Model Catalog stores per-model pricing data, enabling precise cost calculation.
- **Capability-based routing:** The evaluation pipeline can filter models by capability (`["vision", "tool_calling"]`) before running. This is essential for multi-modal and agent evaluation.
- **Graceful deprecation:** A model can be marked as deprecated in the catalog without removing the provider adapter. Users are warned when selecting a deprecated model.
- **Data-driven model management:** Adding a new model to an existing provider requires a database insert, not code changes. This enables non-engineer team members to manage the model catalog.
- **Consumer transparency:** API responses and reports include both provider_name and model_name, enabling precise per-model analysis.

**Alternatives considered:**
- **Providers as the only abstraction:** Model metadata embedded in provider config JSONB. Querying "which models support vision" requires scanning all provider configurations. No structured pricing or capability data.
- **Hardcoded model lists in provider adapters:** Every model addition requires a code change and redeploy. Not scalable for a community project.

**Consequences:** Database schema is slightly more complex (new `provider_models` table + relationship). The provider adapter's `generate()` method now accepts a `model_name` parameter in addition to `provider_name`. All existing provider adapters must declare their model lists during the migration.

---

## ADR-019: Experiment Hierarchy

**Status:** Accepted

**Context:** Users need to group related evaluation runs for comparison. A flat `Project → EvaluationRun` hierarchy makes it impossible to ask "which model performed better in my summarization experiment?"

**Decision:** Introduce `Experiment` as a container for related evaluation runs. New hierarchy: `Workspace → Project → Experiment → EvaluationRun`.

**Reasoning:**
- **Comparative analysis:** An experiment groups runs that test a hypothesis. Users can compare runs within an experiment and compute deltas from a baseline.
- **Organizational clarity:** "GPT-4 vs Claude on summarization" is an experiment. It contains 2+ evaluation runs (one per model). This maps to how engineers think about A/B testing.
- **Decision tracking:** Experiments have a `conclusion` field. Teams can document why a particular model was chosen, creating an institutional memory of evaluation decisions.
- **Backward compatibility:** The `experiment_id` column is nullable. Existing runs without an experiment continue to work. The project page shows all runs. The experiment page shows grouped runs.

**Alternatives considered:**
- **Tags for grouping:** Tags are unstructured. Cannot enforce that runs in the same experiment use the same dataset version. No baseline concept.
- **Folders within projects:** Folder abstractions are UI-only. The API has no concept of relationships between runs.

**Consequences:** All evaluation run creation endpoints accept an optional `experiment_id`. The reporting module must support experiment-level aggregation. Migration script adds `experiment_id` to `evaluation_runs` (nullable).

---

## ADR-020: Evaluation Profiles as Data

**Status:** Accepted

**Context:** Different evaluation scenarios (quick dev check, pre-deployment safety gate, RAG evaluation, cost analysis) require different metric combinations, thresholds, and concurrency settings. Without profiles, users must manually configure every evaluation run.

**Decision:** Introduce `EvaluationProfile` as a reusable, database-stored configuration template. Profiles define metrics, thresholds, providers, concurrency, and timeouts.

**Reasoning:**
- **Reusability:** A "Safety" profile is configured once and reused across all projects. Configuration is not duplicated in every evaluation run.
- **Consistency:** Teams standardize on profiles for different deployment stages. "Production Gate" always runs the same metrics with the same thresholds.
- **Override at run time:** A profile provides defaults; the user can override specific values when creating a run. This supports both standardization and flexibility.
- **Built-in + custom:** Six built-in profiles (Quick, Safety, RAG, Cost, Regression, Production Gate) ship with the platform. Users can extend them or create new ones.
- **Profile inheritance:** Custom profiles can extend built-in ones, inheriting their configuration and overriding specific values.

**Alternatives considered:**
- **Manual configuration per run:** High cognitive load. Inconsistent evaluations across teams.
- **Code-defined profiles:** Require code changes to add/modify profiles. Not accessible to non-engineers.
- **Environment variable-based configuration:** Not multi-tenant. Does not scale to many profiles.

**Consequences:** New `evaluation_profiles` table. Evaluation run creation accepts an optional `profile_id`. Resolved configuration merges profile defaults with run overrides. Migration: seed built-in profiles. System profiles are read-only; custom profiles are user-managed.

---

## ADR-021: Domain-Driven Design with Bounded Contexts

**Status:** Accepted

**Context:** As the project grows beyond a handful of modules, the risk of circular dependencies and unclear ownership increases. The initial flat module structure had no clear boundaries between contexts.

**Decision:** Organize the codebase using Domain-Driven Design with explicit bounded contexts. Each context has its own entities, services, repositories, events, and (optionally) workflows.

**Bounded contexts identified:**

| Context        | Core Entity      | Primary Events                               |
|---------------|------------------|----------------------------------------------|
| Identity       | User, Team       | UserRegistered, TeamCreated, MemberRoleChanged |
| Project        | Project, Prompt  | PromptVersionCreated                         |
| Dataset        | Dataset, Row     | DatasetUploaded, DatasetVersionCreated       |
| Evaluation     | Experiment, Run  | EvaluationStarted, EvaluationCompleted        |
| Metrics        | MetricDefinition | MetricComputed, ThresholdBreached            |
| Red Team       | Campaign, Finding| FindingDetected, CampaignCompleted           |
| Providers      | ProviderSettings | ProviderConnected, ModelDeprecated           |
| Reporting      | Report           | ReportGenerated                              |
| Notifications  | Webhook          | WebhookDelivered, NotificationFailed         |

**Reasoning:**
- **Explicit boundaries:** Each context has a clear purpose and owned data. No more "I don't know where to put this service."
- **Event-driven communication:** Contexts communicate through events, not direct imports. This prevents circular dependencies.
- **Independent evolution:** A context can be refactored, or even extracted into a separate microservice, without affecting other contexts — as long as the event contracts are maintained.
- **Team scaling:** Each bounded context maps to a potential team ownership boundary. As the project grows, different contributors can own different contexts.
- **Testability:** Contexts can be unit-tested in isolation with mocked event buses and repositories.

**Alternatives considered:**
- **Layered architecture (flat modules):** Works well for small projects but leads to dependency spaghetti as the codebase grows. No clear ownership boundaries.
- **Microservices from day one:** Premature. The bounded context approach allows modular monolith deployment with a clear path to service extraction if needed.

**Consequences:** The folder structure is deeper (`contextual/evaluation/entities/` vs `domain/evaluations.py`). More files, but each file has a clearer responsibility. Team onboarding requires understanding DDD terminology. The event bus becomes the primary inter-context communication mechanism, which is an architectural shift from direct service calls.

---

## ADR-009: Evaluation Results as Immutable Records

**Status:** Accepted

**Context:** Evaluation results inform deployment decisions. They must be auditable and verifiable after the fact.

**Decision:** Metric results and evaluation tasks are append-only. No UPDATE or DELETE operations on completed records.

**Reasoning:**
- **Audit trail:** Every score is permanently recorded with a timestamp. There is no way to retroactively alter results.
- **Reproducibility:** Given the same prompt, dataset version, provider config, and metric version, the same score should result. Immutability prevents silent data corruption.
- **Simplicity:** No need for complex locking or optimistic concurrency for evaluation records.

**Implementation:** `evaluation_tasks` and `metric_results` tables have no UPDATE triggers in the application. Soft deletes via `deleted_at` are the only allowed mutation.

**Consequences:** Storage grows monotonically. Mitigated by table partitioning and configurable retention policies for raw data.

---

## ADR-010: DeepEval as the Primary Metrics Library

**Status:** Accepted

**Context:** Building evaluation metrics from scratch is high-effort and error-prone. We need a library with comprehensive, validated implementations.

**Decision:** Use DeepEval as the primary metrics computation library, wrapped behind our `BaseMetric` interface.

**Reasoning:**
- **Breadth:** 20+ built-in metrics covering hallucination, faithfulness, relevancy, toxicity, bias, and more.
- **Modularity:** Each metric is an independent class — easy to wrap individually.
- **Evaluator model agnostic:** Supports GPT-4, Claude, or local models as the judge.
- **Active development:** Regular releases, growing community.
- **Apache 2.0 license:** Compatible with our open-source goals.

**Alternatives considered:**
- **Built-from-scratch metrics:** Correctly implementing LLM-as-judge metrics requires extensive prompt engineering and validation. High maintenance cost.
- **RAGAS:** RAG-specific. Does not cover safety metrics (toxicity, bias, jailbreak).
- **LangChain evaluation module:** Coupled to LangChain runtime. Fewer metrics.

**Consequences:** DeepEval's API changes will require wrapper updates. The adapter layer insulates the domain from these changes.

---

## ADR-011: UUIDv7 for Primary Keys

**Status:** Accepted

**Context:** Primary keys must be unique across distributed systems, prevent enumeration, and support efficient B-tree indexing.

**Decision:** Use UUIDv7 for all primary keys.

**Reasoning:**
- **Time-sortable:** UUIDv7 embeds a millisecond-precision timestamp, making primary key inserts append-heavy on B-tree indexes (unlike UUIDv4's random ordering).
- **No enumeration:** Unlike auto-increment integers, UUIDs cannot be guessed.
- **Distributed-friendly:** Workers can generate IDs without database round trips.
- **Readable ordering:** Newer records have lexicographically larger UUIDs.

**Alternatives considered:**
- **Auto-increment integers:** Enumeration risk. Conflicts in distributed scenarios.
- **UUIDv4:** Random ordering causes B-tree page splits and index fragmentation.
- **ULID:** Less standard than UUID. Fewer library implementations.

**Consequences:** UUIDs are bulkier than integers (16 bytes vs. 4–8 bytes). Index size is larger, but this is acceptable for our data volume.

---

## ADR-012: Configuration as Data

**Status:** Accepted

**Context:** Evaluation configurations (which metrics, providers, thresholds) change frequently and should not require code changes or redeploys.

**Decision:** Store all evaluation configurations in the database, not in code or environment variables.

**Reasoning:**
- **Auditability:** Configuration changes are tracked via the audit log. Who changed what, and when.
- **Multi-tenancy:** Different projects can have different metrics, thresholds, and providers without code branches.
- **API-driven:** Frontend and CI/CD integration can configure evaluations without touching the server filesystem.
- **Rollback:** Previous configurations are accessible via the evaluation run's stored configuration snapshot.

**Implementation:** Each `evaluation_run` record stores the full configuration as a JSONB snapshot at creation time. Changes to default configurations do not retroactively alter completed evaluations.

**Consequences:** Database schema must support JSONB configuration storage. Slightly more complex queries to resolve default vs. override configurations.

---

## ADR-013: Open Source with Apache 2.0 License

**Status:** Proposed

**Context:** RedOps Eval is an open-source project intended for community adoption and contribution.

**Decision:** License under Apache 2.0.

**Reasoning:**
- Permissive enough for enterprise adoption.
- Includes patent grant.
- Compatible with all third-party dependencies in our stack.
- Standard license in the AI/ML tooling ecosystem.

**Alternatives considered:**
- **MIT:** Simpler, but lacks patent protection.
- **AGPL:** Restrictive. Would deter enterprise adoption and contributions from corporate contributors.
- **BSL / source-available:** Defeats the purpose of a community open-source project.

**Consequences:** Apache 2.0 is the standard choice for infrastructure-style open-source projects. No unexpected consequences.
