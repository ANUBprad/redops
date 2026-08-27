# RedOps Eval — Architecture

## Overall System Architecture

RedOps Eval follows an **event-driven, workflow-orchestrated** monorepo architecture with a **React SPA frontend**, a **FastAPI backend**, a **PostgreSQL database**, and a **Temporal workflow engine**. The backend is organized into domain modules following Domain-Driven Design with bounded contexts. The **Temporal workflow engine** replaces Celery as the durable orchestration layer for all long-running operations. An **Event Bus** decouples domain services through asynchronous event publishing. The **provider abstraction** separates LLM providers from their models, capabilities, and pricing. The **evaluator abstraction** decouples metrics from underlying evaluation libraries (DeepEval, RAGAS, etc.).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          React SPA (Vite)                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ Dashboard│ │ Projects │ │Datasets  │ │Experiments│ │ Profiles     │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ Reports  │ │ Red Team │ │ Providers│ │ Models   │ │ Settings/Auth│ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────┘ │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ REST API (HTTP / WebSocket)
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    FastAPI Gateway Layer (Stateless)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────────────┐ │
│  │ Auth MW  │ │ Rate Lim │ │ Validate │ │ CORS / Structured Logging │ │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Workflow Engine (Temporal)                             │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Workflow Definitions (durable, fault-tolerant execution)        │   │
│  │                                                                  │   │
│  │  ┌────────────────────┐  ┌────────────────────┐                 │   │
│  │  │ EvaluationWorkflow │  │ RedTeamWorkflow    │                 │   │
│  │  │ 1. Resolve config  │  │ 1. Load adversarial│                 │   │
│  │  │ 2. Fan-out tasks   │  │ 2. Execute probes  │                 │   │
│  │  │ 3. Await completions│  │ 3. Score responses │                 │   │
│  │  │ 4. Aggregate scores │  │ 4. Classify findings│                 │   │
│  │  │ 5. Evaluate thresholds│ │ 5. Update campaign │                 │   │
│  │  │ 6. Publish events  │  │ 6. Publish events  │                 │   │
│  │  └────────────────────┘  └────────────────────┘                 │   │
│  │  ┌────────────────────┐  ┌────────────────────┐                 │   │
│  │  │ ExportWorkflow     │  │ ScheduledEvalWf    │                 │   │
│  │  │ 1. Query data      │  │ 1. Wait for cron   │                 │   │
│  │  │ 2. Generate file   │  │ 2. Start EvalWf    │                 │   │
│  │  │ 3. Upload to S3    │  │ 3. Loop            │                 │   │
│  │  └────────────────────┘  └────────────────────┘                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  Temporal features used: Durable timers, automatic retries, event       │
│  history, side effects, cancellation scopes, saga rollbacks.            │
│  Temporal Server stores workflow state in its own PostgreSQL instance.  │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Domain Service Layer                                   │
│  (Synchronous, stateless services called by Temporal Activities)          │
│                                                                          │
│  ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌──────────────┐   │
│  │Project ││Dataset ││Prompt  ││Eval    ││Red Team││ Experiment    │   │
│  │Service ││Service ││Service ││Engine  ││Engine  ││ Manager      │   │
│  └────────┘└────────┘└────────┘└────────┘└────────┘└──────────────┘   │
│  ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌──────────────┐   │
│  │Metric  ││Evaluator││Report  ││Profile ││Provider││ Model        │   │
│  │Registry││Registry││Service ││Manager ││Registry││ Catalog      │   │
│  └────────┘└────────┘└────────┘└────────┘└────────┘└──────────────┘   │
│                                                                          │
│  Services do NOT call each other directly. They publish domain events    │
│  via the Event Bus. Temporal Activities call services, not vice versa.  │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Event Bus (Redis Streams)                               │
│                                                                          │
│  Publishers:                    Topics:                    Subscribers:  │
│  ┌──────────┐                  ┌───────────────────┐      ┌──────────┐ │
│  │ EvalEng. │─ EvaluationCompleted ─▶│ WebhookWorker  │ │
│  ├──────────┤                  ├───────────────────┤      ├──────────┤ │
│  │Metrics   │─ MetricComputed ─▶│ ReportRefresh   │ │
│  ├──────────┤                  ├───────────────────┤      ├──────────┤ │
│  │Providers │─ ProviderConnected ─▶│ AuditLogger     │ │
│  ├──────────┤                  ├───────────────────┤      ├──────────┤ │
│  │Red Team  │─ FindingDetected ─▶│ NotificationSvc │ │
│  └──────────┘                  ├───────────────────┤      └──────────┘ │
│                                │ ThresholdBreached│                     │
│                                ├──────────────────┤                     │
│                                │ DatasetUploaded  │                     │
│                                └──────────────────┘                     │
│                                                                          │
│  Events are durable (Redis Streams with consumer groups). At-least-once  │
│  delivery. Dead-letter queue for failed processing.                      │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
              ┌───────────┴───────────┐
              ▼                       ▼
┌────────────────────┐  ┌──────────────────────────────────────┐
│    PostgreSQL      │  │  Temporal Server (+ its own DB)      │
│  (Read-write)      │  └──────────────────────────────────────┘
│                    │
│  ┌──────────────┐  │
│  │  Experiments │  │
│  │  Evaluation  │  │
│  │  Runs        │  │
│  │  Metrics     │  │
│  │  Providers   │  │
│  │  Models      │  │
│  │  Profiles    │  │
│  │  EventLog    │  │
│  │  WorkflowExec│  │
│  └──────────────┘  │
└────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               Provider & Model Layer                                      │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Provider Registry (ABC: BaseProviderAdapter)                      │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐ │   │
│  │  │ OpenAIPr.│ │ AnthropPr│ │ GeminiPr│ │ Ollama / Groq / OR   │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Model Catalog (each Provider exposes N models)                   │   │
│  │  Model has: Capabilities(list), Pricing(obj), RateLimits(obj),   │   │
│  │  ContextWindow(int), Metadata(JSONB)                              │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Evaluator Layer                                        │
│                                                                          │
│  Metrics never import DeepEval or RAGAS directly. Instead:               │
│                                                                          │
│  ┌──────────────┐     ┌────────────────┐     ┌───────────────────┐     │
│  │ Hallucination │────▶│ DeepEvalAdapte│────▶│ deepeval library  │     │
│  │ Metric        │     │ r              │     │                   │     │
│  └──────────────┘     └────────────────┘     └───────────────────┘     │
│  ┌──────────────┐     ┌────────────────┐     ┌───────────────────┐     │
│  │ Faithfulness  │────▶│ RAGASAdapter   │────▶│ ragas library     │     │
│  │ Metric        │     │                │     │                   │     │
│  └──────────────┘     └────────────────┘     └───────────────────┘     │
│  ┌──────────────┐     ┌────────────────┐     ┌───────────────────┐     │
│  │ Custom Metric │────▶│ CustomAdapter  │────▶│ user-defined code │     │
│  │ (plugin)      │     │                │     │                   │     │
│  └──────────────┘     └────────────────┘     └───────────────────┘     │
│                                                                          │
│  Evaluator Adapters implement: def evaluate(metric, inputs) -> Score     │
└─────────────────────────────────────────────────────────────────────────┘
```

> **Accuracy note (current implementation):** The adapter classes above
> (`HeuristicAdapter`, `EmbeddingAdapter`, `LLMJudgeAdapter`, `RAGASAdapter`,
> `CustomAdapter`) are defined in `app/evaluation/evaluators/adapters.py` but
> **none is registered into a running `MetricEngine`**. Built-in metrics
> (`ALL_METRICS`) run directly. There is **no `DeepEvalAdapter`**, and `ragas` /
> `deepeval` are **not runtime dependencies** — the `RAGASAdapter` is an optional,
> currently-unwired facade. The diagram above is the intended design, not the
> wired runtime path.

## Layered Architecture

```
┌─────────────────────────────────────────────┐
│          Presentation Layer (React SPA)      │
│   Router → TanStack Query → Components       │
├─────────────────────────────────────────────┤
│          API Gateway Layer (FastAPI)          │
│   Middleware → Validators → Thin Routers     │
├─────────────────────────────────────────────┤
│       Workflow Layer (Temporal)               │
│   Workflow Definitions → Activities          │
├─────────────────────────────────────────────┤
│       Domain Service Layer (Synchronous)     │
│   Business logic, policies, validations      │
├─────────────────────────────────────────────┤
│       Event Bus Layer (Redis Streams)        │
│   Publishers → Topics → Subscribers          │
├─────────────────────────────────────────────┤
│       Data Access Layer (SQLAlchemy Async)   │
│   Repositories → Unit of Work → Migrations  │
├─────────────────────────────────────────────┤
│       Infrastructure Layer                    │
│   PostgreSQL, Temporal, Redis, S3, Providers │
└─────────────────────────────────────────────┘
```

## Backend Responsibilities

- **API Gateway** — Authenticate, rate-limit, validate, route requests. No business logic.
- **Workflow Orchestration (Temporal)** — Define durable, fault-tolerant workflows for evaluation runs, red-team campaigns, exports, and scheduled tasks. Handle retries, timeouts, sagas, and state persistence automatically.
- **Domain Services** — Synchronous business logic. Called by Temporal Activities, never directly by the API gateway. Services publish domain events to the Event Bus after state changes.
- **Event Bus** — Decouple domain services via asynchronous event publishing. EvaluationCompleted triggers webhooks, report refresh, notifications — without Evaluation Engine knowing about any of them.
- **Provider Abstraction + Model Catalog** — Maintain a registry of LLM provider adapters. Separate the concept of Provider (OpenAI) from Model (gpt-4o) from Capabilities (text, vision, tool_calling) from Pricing (per-token cost).
- **Evaluator Abstraction** — Decouple metric computation from underlying evaluation libraries (DeepEval, RAGAS, custom). Metrics request evaluation; the Evaluator Registry dispatches to the correct adapter.
- **Metrics Plugin System** — Metrics are pluggable, versioned, and discoverable. Each metric declares its inputs, evaluator requirements, and category.
- **Data Persistence** — All evaluation results, configurations, datasets, and user data stored in PostgreSQL.
- **Reporting** — Aggregate metric data into time-series views, comparison reports, and export formats.

## Frontend Responsibilities

- **Dashboard** — Real-time project overview, recent evaluation runs, system health.
- **Project Management** — CRUD for projects, environments, and API keys.
- **Dataset Management** — Upload, preview, version datasets in JSON/CSV.
- **Prompt Management** — Version-controlled prompt templates with variables.
- **Evaluation Runner** — Configure runs, select metrics, pick providers, trigger execution, watch progress.
- **Report Viewer** — Tabular and chart-based views of evaluation results, side-by-side model comparisons.
- **Red Team Console** — Configure adversarial campaigns, review findings, track regression.
- **Settings** — Provider credentials, user management, webhooks, notification preferences.

## Evaluation Pipeline

```
User Triggers Run via API (or CI/CD, or Schedule)
       │
       ▼
1. API Gateway: Authenticate & Validate
   └─ POST /projects/{id}/evaluations
   └─ Validate payload → return 202 Accepted with run_id
   └─ Publish EvaluationStarted event
       │
       ▼
2. Start Temporal Workflow (EvaluationWorkflow)
   └─ Temporal creates workflow execution with run_id
   └─ Workflow survives process restarts (durable execution)
       │
       ▼
3. Activity: Resolve Configuration
   └─ Load experiment / profile settings
   └─ Resolve prompt version + dataset version
   └─ Resolve metric list from profile
   └─ Resolve provider + model list
       │
       ▼
4. Activity: Fan-out Prompt Executions
   └─ For each (dataset_row, provider, model) combination:
       ├─ Call provider_adapter.generate(prompt, model_config)
       ├─ Record raw response, latency_ms, token counts, cost_usd
       ├─ Persist EvaluationTask record
       └─ Publish TaskCompleted event → WebSocket → UI
   └─ Temporal parallel: all combinations execute concurrently
   └─ Partial failure: failed tasks recorded, non-failed continue
       │
       ▼
5. Activity: Compute Metrics
   └─ For each (evaluation_task, metric) configured:
       ├─ Look up metric in MetricRegistry → get MetricDefinition
       ├─ Resolve metric from registry → run via MetricEngine
       ├─ (External evaluator adapters such as RAGAS are defined but not wired)
       ├─ Call evaluator.evaluate(metric, inputs)
       ├─ Persist MetricResult (immutable)
       └─ Publish MetricComputed event
   └─ Temporal parallel: metrics computed concurrently per task
       │
       ▼
6. Activity: Aggregate & Finalize
   └─ Aggregate metric results into run-level summaries
   └─ Evaluate threshold checks
   └─ Update EvaluationRun status = completed (or failed)
   └─ Publish EvaluationCompleted event → Event Bus
       │
       ▼
7. Event Bus Triggers Side Effects (async, non-blocking)
   ├─ WebhookWorker → deliver to configured URLs
   ├─ ReportRefreshWorker → update materialized views
   ├─ NotificationWorker → send email/Slack notification
   ├─ AuditLogger → record completion in audit log
   └─ ThresholdWorker → if breached, publish ThresholdBreached
```

## Data Flow

```
[Dataset Upload]     → DatasetService → Event DatasetUploaded → subscribers
[Prompt Create]      → PromptService → Event PromptVersionCreated → subscribers
[Run Trigger]        → API → Temporal.StartWorkflow(EvaluationWorkflow...)
[Activity: Execute]  → ProviderAdapter.generate() → EvaluationTask persisted
[Activity: Compute]  → Evaluator.evaluate(metric, inputs) → MetricResult persisted
[Activity: Finalize] → Aggregate → publish EvaluationCompleted → Event Bus
[Event Bus]          → WebhookWorker → HTTP POST to webhook URLs
[Event Bus]          → ReportRefreshWorker → materialized view refresh
[Report View]        → ReportService → aggregate query → JSON response
[Export]             → Temporal.StartWorkflow(ExportWorkflow) → file → download
```

## Extension Points

1. **Provider Adapters** — Implement `BaseProviderAdapter` and register. No other code changes. Each provider declares its available models in the Model Catalog.
2. **Model Catalog Entries** — Add new models to existing providers via configuration (no code). Pricing, rate limits, capabilities, and context window are data, not code.
3. **Custom Metrics (Plugin)** — Package a `BaseMetric` subclass with a `pyproject.toml` entry point. The MetricRegistry discovers it at startup. Supports versioning, metadata, and categorized listing.
4. **Evaluator Adapters** — Implement `BaseEvaluatorAdapter` to integrate a new evaluation library (e.g., Azure AI Evaluation SDK). Metrics are automatically routed to the correct evaluator.
5. **Event Subscribers** — Register new subscribers to any domain event. No changes to event publishers needed. This is the primary mechanism for adding side effects.
6. **Workflow Definitions** — Write new Temporal Workflows for custom evaluation scenarios. Existing Activities (provider calls, metric computation) are reusable.
7. **Evaluation Profiles** — Define new profiles in configuration (Quick, Safety, RAG, Regression, Production Gate). Each profile is a data-driven template.
8. **Dataset Importers** — Implement `DatasetImporter` for custom formats.
9. **Authentication Backends** — Replace JWT/auth with OAuth2, SAML, or LDAP via the auth provider interface.
10. **Interaction Model Extensions** — Add new interaction types (agent, multi-turn, tool-calling) by extending the Interaction model without changing the evaluation pipeline.

## Design Principles

1. **Workflow-First Orchestration** — All multi-step, long-running, or failure-sensitive operations are Temporal Workflows. No background threads, no in-process task queues.
2. **Event-Driven Decoupling** — Domain services communicate through events, not direct calls. This prevents circular dependencies and enables independent evolution of bounded contexts.
3. **Provider Neutrality + Model Awareness** — No provider logic leaks into the domain. But models are first-class entities with known capabilities, enabling intelligent routing.
4. **Evaluator Abstraction** — Metrics depend on an evaluator interface, not on DeepEval or any specific library. Evaluation libraries are swappable infrastructure.
5. **Async by Default** — All I/O is asynchronous. Temporal handles the durable execution; the API server stays responsive.
6. **Immutable Audit Trail** — Evaluation runs, metric results, and event log entries are append-only. No updates; only inserts.
7. **Fail Observable** — Every provider call is wrapped in structured error handling. Temporal retries transient failures. Permanent failures produce partial results, not silent omissions.
8. **Configuration as Data** — Experiments, profiles, thresholds, model metadata — all stored in the database, not in code.
9. **Thin Frontend, Fat API** — The frontend is a view layer. The API is fully consumable without the UI.
10. **Defense in Depth** — Rate limiting, input validation at every layer, parameterized queries, no raw SQL, credential rotation, audit logging.

## Experiments & Profiles

### Hierarchy

```
Workspace (Team)
  └── Project
       └── Experiment (hypothesis: "Claude 3.5 is more factual than GPT-4o")
            ├── EvaluationRun (config: profile=rag, dataset=v3, prompt=v2, providers=[...])
            ├── EvaluationRun (config: profile=rag, dataset=v3, prompt=v2, providers=[...])
            └── EvaluationRun (config: profile=safety, dataset=v1, prompt=v2, providers=[...])
```

**Experiment** represents a hypothesis or question the user wants to answer. An experiment groups related evaluation runs so that results can be compared, trends tracked, and decisions recorded.

**Migration from old model:** Previously `Project → EvaluationRun`. Now `Project → Experiment → EvaluationRun`. The old `evaluation_runs.project_id` is preserved; `experiment_id` is added. Backward-compatible via nullable experiment_id.

### Evaluation Profiles

A **Profile** is a reusable configuration template that defines:

- **Metrics** — Which metrics to compute (hallucination, toxicity, latency, cost, etc.)
- **Thresholds** — Pass/fail boundaries per metric
- **Providers / Models** — Which models to evaluate (can be overridden at run time)
- **Concurrency** — Number of parallel provider calls
- **Timeouts** — Per-request and per-run timeouts
- **Evaluator Model** — Which LLM acts as the "judge" (if applicable)

**Built-in profiles:**

| Profile         | Use Case                                    | Metrics                                    |
|----------------|---------------------------------------------|--------------------------------------------|
| Quick          | Rapid iteration during development          | latency, token_usage                       |
| Safety         | Pre-deployment safety gate                  | toxicity, bias, prompt_injection, jailbreak |
| RAG            | Retrieval-Augmented Generation evaluation   | faithfulness, context_precision, context_recall |
| Cost           | Cost optimization analysis                  | cost, latency, token_usage                 |
| Regression     | Compare against previous run baseline       | all metrics with threshold comparison      |
| Production Gate | Full pre-deployment check                  | all metrics + cost + latency with strict thresholds |

Profiles are stored in the database and can be customized per project. Users can create custom profiles or extend built-in ones.

## Future-Proofing Architecture

The initial architecture assumes a simple `prompt → response` interaction model. The following extensions are designed to slot in without architectural redesign.

> **Status:** These Interaction types and integrations below are **planned / designed future
> extensions**, not yet implemented in code. `Interaction` is an abstract concept in this
> document; there is currently no `Interaction` type or `multi_modal`/`multi_agent` workflow in
> the repository. Agent evaluation (`agents/`) and tool-calling contracts exist, but MCP,
> multi-agent topology, long-context segmentation, and multi-modal evaluation remain roadmap
> Phase 11 work (see `docs/ROADMAP.md`).

### Interaction Model (Abstract)

Instead of modeling everything as `prompt_text → response_text`, we introduce an abstract **Interaction**:

```python
class Interaction:
    type: Literal["simple", "conversation", "agent", "tool_call", "multi_modal"]
    inputs: dict  # prompt, messages, image_urls, audio_url, tools, etc.
    outputs: dict # response, tool_results, agent_trace, etc.
```

- **Agent Evaluation**: Interaction type `agent`. Inputs include available tools and max turns. Outputs include the full agent trace and final response. Metrics evaluate tool selection correctness, task completion rate, and efficiency.
- **MCP Servers**: Model Context Protocol servers would be registered as tool providers. The `tool_call` Interaction type would route tool calls through MCP adapters. (Planned — no MCP adapter exists yet.)
- **Multi-Agent Systems**: Interaction type `multi_agent`. Inputs include agent topology (supervisor, workers, routers). Evaluation includes communication efficiency, conflict resolution, and overall task success.
- **Multi-Modal**: Interaction type `multi_modal`. Inputs include image URLs or base64-encoded images and optional audio. Provider adapters check `Capabilities.vision` and `Capabilities.audio` before routing.
- **Long Context**: Provider adapters report `Model.context_window`. The evaluation pipeline can segment inputs exceeding the context window and measure recall degradation across segments.

### Architecture Impact

- **Provider Adapters** already abstract the `generate()` call. Multi-modal inputs are additional fields in the input schema — the adapter layer normalizes them.
- **Evaluator Layer** adapters can be written for agent-specific metrics (tool call accuracy, trajectory coherence) without changing the core metric interface.
- **Temporal Workflows** for agent evaluation simply have more steps (each tool call is a Temporal Activity, allowing the workflow to pause for external side effects).
- **Model Catalog** already tracks capabilities. The evaluation pipeline can filter models by required capabilities before running.
