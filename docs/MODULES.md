# RedOps Eval — Internal Modules

## Module Map (Domain-Driven Design with Bounded Contexts)

```
redops_eval/
├── api/                        # FastAPI application layer
│   ├── app.py                  # App factory
│   ├── middleware/             # Auth, rate-limit, CORS, structured logging
│   └── routes/                 # Thin routers (one per bounded context)
│
├── core/                       # Shared kernel
│   ├── config.py               # Pydantic settings
│   ├── database.py             # Session factory, engine, Unit of Work
│   ├── security.py             # Password hashing, JWT, encryption
│   ├── event_bus.py            # Event bus interface + Redis implementation
│   ├── exceptions.py           # Domain exceptions
│   └── types.py                # Shared value objects (Interaction, ProviderResponse, etc.)
│
├── contextual/                 # Bounded Contexts (DDD)
│   │
│   ├── identity/               # Context: Identity & Access
│   │   ├── entities/           # User, Team
│   │   ├── services/           # AuthService, TokenService, RbacService
│   │   ├── repositories/      # UserRepository, TeamRepository
│   │   ├── events/            # UserRegistered, TeamCreated, MemberRoleChanged
│   │   └── commands/          # RegisterUser, LoginUser, ChangeRole
│   │
│   ├── project/                # Context: Project & Configuration
│   │   ├── entities/           # Project, Prompt, PromptVersion
│   │   ├── services/           # ProjectService, PromptService
│   │   ├── repositories/      # ProjectRepository, PromptRepository
│   │   └── events/            # PromptVersionCreated
│   │
│   ├── dataset/               # Context: Dataset Management
│   │   ├── entities/          # Dataset, DatasetVersion, DatasetRow
│   │   ├── services/          # DatasetService, ImportService
│   │   ├── repositories/     # DatasetRepository
│   │   └── events/           # DatasetUploaded, DatasetVersionCreated
│   │
│   ├── evaluation/            # Context: Evaluation (core domain)
│   │   ├── entities/          # Experiment, EvaluationRun, EvaluationTask
│   │   ├── services/          # EvaluationEngine, ExperimentManager, ProfileManager
│   │   ├── repositories/     # EvaluationRunRepository, ExperimentRepository
│   │   ├── events/           # EvaluationStarted, TaskCompleted, EvaluationCompleted
│   │   └── workflows/        # Temporal workflow definitions
│   │       ├── evaluation_workflow.py
│   │       ├── export_workflow.py
│   │       └── scheduled_eval_workflow.py
│   │
│   ├── metrics/               # Context: Metrics
│   │   ├── domain/            # BaseMetric, MetricDefinition, MetricRegistry
│   │   ├── plugins/           # Built-in metric plugin packages
│   │   │   ├── hallucination/
│   │   │   ├── faithfulness/
│   │   │   ├── toxicity/
│   │   │   ├── bias/
│   │   │   ├── latency/
│   │   │   └── cost/
│   │   ├── services/          # MetricService, ThresholdService
│   │   └── events/           # MetricComputed, ThresholdBreached
│   │
│   ├── red_team/              # Context: Red Teaming
│   │   ├── entities/          # RedTeamCampaign, RedTeamFinding
│   │   ├── services/          # RedTeamEngine, AdversarialGenerator
│   │   ├── repositories/     # CampaignRepository, FindingRepository
│   │   ├── events/           # FindingDetected, CampaignCompleted
│   │   └── workflows/        # red_team_workflow.py
│   │
│   ├── providers/             # Context: Provider Management
│   │   ├── entities/          # ProviderSettings, ProviderModel
│   │   ├── services/          # ProviderRegistry, ModelCatalog, CostCalculator
│   │   ├── events/           # ProviderConnected, ModelDeprecated
│   │   └── repository/       # ProviderSettingsRepository
│   │
│   ├── reporting/             # Context: Reporting & Analytics
│   │   ├── entities/          # Report, DashboardWidget
│   │   ├── services/          # ReportService, TrendService, ComparisonService
│   │   └── events/           # ReportGenerated
│   │
│   └── notifications/        # Context: Notifications
│       ├── entities/         # Webhook, NotificationChannel
│       ├── services/         # WebhookService, NotificationDispatcher
│       └── events/           # WebhookDelivered, NotificationFailed
│
├── infrastructure/            # Adapter implementations
│   ├── temporal/              # Temporal client setup, worker registration
│   │   ├── client.py
│   │   ├── worker.py
│   │   └── converters/       # Custom data converters
│   ├── providers/             # Provider adapter implementations
│   │   ├── openai/
│   │   ├── anthropic/
│   │   └── (gemini, ollama, groq, openrouter — planned, Phase 11)
│   ├── evaluators/            # Evaluator adapter implementations
│   │   ├── base.py            # BaseEvaluatorAdapter
│   │   └── adapters.py        # Heuristic/Embedding/LLMJudge/RAGAS/Custom adapters
│   │                          # (RAGAS adapter optional; not wired to any engine)
│   ├── event_bus/             # Event bus implementations
│   │   ├── redis_streams.py   # Redis Streams implementation
│   │   └── in_memory.py       # For testing
│   └── storage/               # File storage backends
│       ├── local.py
│       └── s3.py
│
└── workers/                    # Temporal Activity implementations
    ├── evaluation_activities.py
    ├── provider_activities.py
    ├── metric_activities.py
    └── notification_activities.py
```

---

## Authentication Module (`domain/auth/`)

**Purpose:** Identity and access management.

**Responsibilities:**
- User registration and login (email/password).
- JWT access + refresh token lifecycle.
- API key validation and scoping.
- Role-based access control (RBAC) at the team level.
- Password hashing (bcrypt) and credential encryption (AES-256-GCM).

**Inputs:** Login credentials, JWT tokens, API keys.

**Outputs:** Authenticated request context (`request.user`, `request.team`).

**Dependencies:** `core/security.py`, `core/database.py`.

**Future extensions:** OAuth2 / SSO provider integrations, SCIM provisioning, 2FA/TOTP.

---

## Project Module (`domain/projects/`)

**Purpose:** Project lifecycle and team scoping.

**Responsibilities:**
- CRUD for projects.
- Soft-delete and restore.
- Project-level configuration storage (default settings for evaluations).
- Summary statistics computation for dashboard cards.

**Inputs:** Project create/update payloads, project_id.

**Outputs:** Project records, summary stats.

**Dependencies:** `core/database.py`, Auth module.

**Future extensions:** Project templates, environment (staging/production) segregation within a project.

---

## Prompt Module (`domain/prompts/`)

**Purpose:** Version-controlled prompt template management.

**Responsibilities:**
- CRUD for prompt templates.
- Version creation on every update (immutable version history).
- Variable extraction and validation against prompt templates.
- Template rendering with dataset row substitution.

**Inputs:** Template strings, variable definitions, dataset rows.

**Outputs:** Rendered prompt strings ready for LLM submission.

**Dependencies:** `core/database.py`, Auth module.

**Future extensions:** Prompt testing/sandbox within the UI, prompt chaining, conversation history templates.

---

## Dataset Module (`domain/datasets/`)

**Purpose:** Structured input data for evaluation runs.

**Responsibilities:**
- Upload, parse, and validate datasets (JSON, CSV, JSONL).
- Version management (each upload creates a new version).
- Row-level storage and paginated retrieval.
- Schema inference and column type detection.
- Checksum verification for data integrity.

**Inputs:** File uploads or inline JSON arrays, dataset metadata.

**Outputs:** Stored dataset rows, inferred schema.

**Dependencies:** `core/database.py`, `infrastructure/storage/` (for large files).

**Future extensions:** Auto-generated adversarial datasets, dataset merging, synthetic data generation.

---

## Evaluation Module (`contextual/evaluation/`)

**Purpose:** Orchestrate the end-to-end evaluation pipeline via Temporal Workflows.

**Responsibilities:**
- Create and configure experiments and evaluation runs.
- Define Temporal Workflows for evaluation execution (EvaluationWorkflow).
- Define Temporal Activities for each step (resolve config → execute prompts → compute metrics → aggregate).
- Track run state machine via Temporal's durable execution (no manual state management).
- Publish domain events (EvaluationStarted, TaskCompleted, MetricComputed, EvaluationCompleted).
- Support experiment grouping for comparative analysis.

**Inputs:** Experiment configuration, evaluation profile, prompt version, dataset version, provider/model selections.

**Outputs:** EvaluationRun records, EvaluationTask records, Event Bus events.

**Dependencies:** Prompt, Dataset, Metrics, Providers modules; `infrastructure/temporal/`; `core/event_bus.py`; experiment and profile entities.

**Future extensions:** Agent evaluation workflows, multi-step conversation workflows, human-in-the-loop approval activities.

**Key design decisions:**
- Evaluation Engine does NOT call webhooks, send notifications, or refresh reports. It publishes events. Subscribers handle side effects.
- The Engine is stateless. Temporal manages all workflow state, retries, and timeouts.
- Activities are idempotent (important for Temporal's at-least-once execution guarantees).

---

## Metrics Module (`contextual/metrics/`)

**Purpose:** Plugin-based metric registry and computation.

**Responsibilities:**
- Define `BaseMetric` interface with `compute(inputs) -> MetricOutput` and `metadata() -> MetricMetadata`.
- Maintain `MetricRegistry` — populated at startup from built-in metrics and discovered plugins (Python entry points).
- Support metric versioning (each MetricDefinition has a semver version).
- Support metric categories (safety, performance, cost, custom) for profile-based filtering.
- Route computation to the correct `EvaluatorAdapter` via the Evaluator Registry.
- Normalize all scores to a 0–1 scale.
- Evaluate thresholds against computed scores.
- Publish `MetricComputed` event after each metric result is persisted.

**Inputs:** EvaluationTask data, MetricDefinition reference, Evaluator selection.

**Outputs:** MetricResult records, MetricComputed events.

**Dependencies:** `infrastructure/evaluators/` (not DeepEval directly — always through the Evaluator abstraction). Providers module for evaluator model calls.

**Plugin Architecture:**
```python
# A metric plugin is a Python package with:
# pyproject.toml: [project.entry-points."redops.metrics"] my_metric = "my_package.metrics:MyMetric"
#
# class MyMetric(BaseMetric):
#     name = "custom_score"
#     version = "1.0.0"
#     category = MetricCategory.CUSTOM
#     required_inputs = ["prompt", "response"]
#     evaluator_type = EvaluatorType.CUSTOM
#
#     async def compute(self, inputs: MetricInputs, evaluator: BaseEvaluatorAdapter) -> MetricOutput:
#         ...
```

**Future extensions:**
- Metric composition (composite metric that averages or weights sub-metrics).
- Multi-turn conversation metrics.
- Code generation evaluation (unit test pass rate).
- Community metric registry for sharing plugins.

### Built-in Metrics

| Metric               | Source         | Type         | Required Inputs                       |
|---------------------|---------------|-------------|---------------------------------------|
| Hallucination       | DeepEval      | LLM-based   | prompt, response, context             |
| Faithfulness        | DeepEval      | LLM-based   | response, context                     |
| Answer Relevancy    | DeepEval      | LLM-based   | prompt, response                      |
| Context Precision   | DeepEval      | LLM-based   | prompt, response, context             |
| Context Recall      | DeepEval      | LLM-based   | prompt, response, context             |
| Toxicity            | DeepEval      | LLM-based   | response                              |
| Bias                | DeepEval      | LLM-based   | prompt, response                      |
| Prompt Injection    | Custom        | Heuristic   | prompt, response                      |
| Jailbreak           | Custom        | LLM-based   | prompt, response                      |
| Latency             | Custom        | Direct      | evaluation_task.latency_ms            |
| Cost                | Custom        | Direct      | evaluation_task.cost_usd              |
| Token Usage         | Custom        | Direct      | evaluation_task.token_count_*         |

---

## Red Team Module (`contextual/red_team/`)

**Purpose:** Automated adversarial evaluation campaigns.

**Responsibilities:**
- Campaign configuration (strategy, target model, adversarial dataset).
- Scheduled campaign execution via Temporal cron workflows (replaces Celery Beat).
- Generate adversarial prompt variations from base datasets.
- Execute evaluation runs under the hood with specialized safety metrics.
- Triage and severity classification of findings.
- Track regression across campaign iterations.
- Publish events: FindingDetected, CampaignCompleted.

**Inputs:** Campaign configuration, adversarial datasets, target provider.

**Outputs:** RedTeamCampaign records, RedTeamFinding records, domain events.

**Dependencies:** Evaluation module, Metrics module, Providers module, Temporal, Event Bus.

**Future extensions:**
- Community-contributed adversarial dataset registry.
- Adaptive red teaming (next prompt depends on previous response).
- Multi-turn conversation-based jailbreak attempts.

---

## Workflow Engine (`contextual/evaluation/workflows/`)

**Purpose:** Define durable, fault-tolerant Temporal Workflows for all long-running operations.

**Responsibilities:**
- Define `EvaluationWorkflow` — the primary workflow that orchestrates an evaluation run:
  1. Resolve configuration (experiment, profile, prompt, dataset, providers).
  2. Fan-out prompt execution activities across all (row, provider, model) combinations in parallel.
  3. Await all task completions (or handle partial failures).
  4. Fan-out metric computation activities across all (task, metric) combinations in parallel.
  5. Aggregate results and evaluate thresholds.
  6. Publish EvaluationCompleted event.
- Define `RedTeamWorkflow` — orchestrates a red-team campaign with dynamic adversarial generation.
- Define `ExportWorkflow` — generates and delivers export files for large result sets.
- Define `ScheduledEvaluationWorkflow` — cron-triggered recurring evaluation runs.
- Every workflow uses Temporal's durable timers, retries, saga patterns, and cancellation scopes.

**Inputs:** Workflow parameters (entity IDs, configuration overrides).

**Outputs:** Workflow execution state (managed by Temporal Server).

**Dependencies:** Temporal Server + Client. Domain service Activities.

**Future extensions:**
- Agent evaluation workflows with multi-step tool-calling loops.
- Human-in-the-loop workflows (pause for approval before proceeding).
- Multi-model comparison workflows (A/B test across N models simultaneously).

---

## Event Bus (`core/event_bus.py`)

**Purpose:** Asynchronous, decoupled communication between bounded contexts.

**Responsibilities:**
- Define the `EventBus` interface: `publish(topic, event)`, `subscribe(topic, handler)`.
- Provide a Redis Streams implementation for production:
  - Topics map to Redis Stream keys.
  - Consumer groups for load-balanced subscriber processing.
  - At-least-once delivery guarantees.
  - Dead-letter queue for failed events (retry 3x, then DLQ).
  - Message TTL for automatic cleanup.
- Provide an in-memory implementation for testing (synchronous publish, no persistence).
- Support correlation IDs across event chains (for distributed tracing).

**Events defined (initial set):**

| Event                  | Publisher            | Subscribers                                  |
|------------------------|----------------------|----------------------------------------------|
| EvaluationStarted     | Evaluation Engine    | (metrics, future: active run tracking)       |
| EvaluationCompleted   | Evaluation Engine    | Webhooks, Report Refresh, Audit Log, Threshold Check |
| MetricComputed        | Metrics Module       | (metrics, future: real-time dashboard)       |
| TaskCompleted         | Evaluation Engine    | WebSocket → UI                               |
| ThresholdBreached     | Metrics Module       | Webhooks, Notification Service               |
| FindingDetected       | Red Team Engine      | Webhooks, Notification Service               |
| CampaignCompleted     | Red Team Engine      | Report Refresh, Audit Log                    |
| ProviderConnected     | Providers Module     | Audit Log                                    |
| DatasetUploaded       | Dataset Module       | (future: auto-indexing)                      |
| PromptVersionCreated  | Prompt Service       | Audit Log                                    |
| ExperimentCompleted   | Evaluation Module    | Report Refresh, Notification Service         |

**Inputs:** Domain events (Python dataclasses/Pydantic models).

**Outputs:** Redis Stream entries → subscriber handlers.

**Dependencies:** Redis (for production), `core/types.py` (event schemas).

**Future extensions:**
- Event sourcing for the audit log (events as the source of truth).
- Event replay for debugging / catch-up subscriptions.
- Schema registry for event versioning (Avro/Protobuf).

---

## Experiment Manager (`contextual/evaluation/`)

**Purpose:** Manage the Experiment lifecycle and comparative analysis.

**Responsibilities:**
- CRUD for experiments within a project.
- Link experiments to evaluation runs.
- Track experiment status (draft → active → completed → archived).
- Support baseline run selection for comparison.
- Compute difference metrics between baseline and experimental runs.
- Record experiment conclusions (manual analysis results).
- Publish ExperimentCompleted event when all runs in an experiment finish.

**Inputs:** Experiment configuration, run IDs.

**Outputs:** Experiment records, baseline comparison data.

**Dependencies:** Evaluation Engine, Reporting module, `core/database.py`.

**Future extensions:**
- Automated experiment analysis (AI-generated conclusions).
- Statistical significance testing between runs.

---

## Profile Manager (`contextual/evaluation/`)

**Purpose:** Manage Evaluation Profiles — reusable configuration templates.

**Responsibilities:**
- CRUD for evaluation profiles (system-level + project-level + custom).
- Profile validation (ensure referenced metrics and thresholds exist).
- Profile inheritance (custom profiles can extend built-in ones).
- Profile sharing across projects within a team.
- Resolve effective configuration at evaluation time (merge profile defaults with run overrides).

**Inputs:** Profile configuration, project context.

**Outputs:** Resolved evaluation configuration (metrics, thresholds, concurrency, timeouts, evaluator model).

**Dependencies:** Metrics Registry, Providers module (for default model selections).

**Future extensions:**
- Profile versioning (track changes to profiles over time).
- Profile import/export for sharing across teams.
- AI-suggested profiles based on dataset analysis.

---

## Evaluator Registry (`infrastructure/evaluators/`)

**Purpose:** Decouple metrics from evaluation library implementations.

**Responsibilities:**
- Define `BaseEvaluatorAdapter` interface:
  ```python
  class BaseEvaluatorAdapter(ABC):
      @abstractmethod
      async def evaluate(
          self,
          metric: BaseMetric,
          inputs: MetricInputs,
          config: EvaluatorConfig
      ) -> MetricOutput: ...
      
      @property
      @abstractmethod
      def supported_metrics(self) -> list[str]: ...
      
      @property
      @abstractmethod
      def evaluator_type(self) -> EvaluatorType: ...
  ```
- Maintain `EvaluatorRegistry` — maps metric names to evaluator adapters.
- Provide built-in adapters (see `adapters.py`):
  - `HeuristicAdapter` — deterministic checks.
  - `EmbeddingAdapter` — embedding/similarity checks.
  - `LLMJudgeAdapter` — LLM-as-judge checks.
  - `RAGASAdapter` — optional RAGAS wrapper (RAG metrics); `ragas` is NOT a
    runtime dependency and no adapter is currently registered into a
    `MetricEngine`, so RAGAS/DeepEval are not used by the built-in metrics.
  - `CustomAdapter` — executes user-provided evaluation code.
- Handle adapter-specific error translation and timeout wrapping.
- Support evaluator model configuration (which LLM acts as the judge).

**Inputs:** Metric definition + evaluation inputs + evaluator config.

**Outputs:** MetricOutput (score, explanation, sub-scores).

**Dependencies:** None to external libraries at the interface level. Adapter implementations depend on their respective libraries (DeepEval, RAGAS).

**Future extensions:**
- Azure AI Evaluation SDK adapter.
- LangSmith evaluation adapter.
- Remote evaluator service (evaluate via API for sensitive environments).
- Ensemble evaluation (run multiple evaluators and average/synthesize results).

---

## Provider Module (`contextual/providers/`)

**Purpose:** Abstract LLM provider interaction and model catalog management.

**Responsibilities (Provider side):**
- Define `BaseProviderAdapter` ABC with `generate`, `generate_stream`, `metadata` methods.
- Implement concrete adapters for each supported provider.
- Maintain the provider registry (dynamic lookup by name).
- Handle provider-specific authentication, rate limiting, and retry logic.
- Normalize responses into a common `ProviderResponse` schema.

**Responsibilities (Model side):**
- Maintain the **Model Catalog** — each provider exposes zero or more models.
- Each model has explicit **Capabilities** (`["text", "vision", "audio", "tool_calling", "streaming"]`).
- Each model has **Pricing** (`input_per_million_tokens`, `output_per_million_tokens`, `per_request`).
- Each model has **Rate Limits** (`rpm`, `tpm`, `max_concurrent`).
- Each model has **Context Window** (`max_tokens`).
- Each model has **Metadata** (`release_date`, `deprecation_status`, `documentation_url`).
- The CostCalculator computes cost from token counts using the model's pricing entry.
- The ModelCatalog supports capability-based filtering (e.g., "only models with vision support").

**Separation rationale:** A provider (OpenAI) is not a model (gpt-4o, gpt-4-turbo). Mixing them prevents accurate cost tracking, capability-aware routing, and future model deprecation handling. By separating them, the evaluation pipeline can:
1. Filter models by required capabilities before running.
2. Accurately compute cost per model without hardcoded pricing tables.
3. Mark models as deprecated without removing the provider adapter.
4. Support model-specific parameters (different context windows, different rate limits).

**Inputs:** Rendered prompt string, provider_config + model_config (model name, temperature, max_tokens, etc.).

**Outputs:** `ProviderResponse(prompt, response, latency_ms, token_count_prompt, token_count_completion, cost_usd, provider_name, model_name)`.

**Dependencies:** `core/security.py` (credential decryption). `core/database.py` (model catalog data).

**Future extensions:**
- Streaming response for real-time evaluation.
- Capability-based auto-routing (choose best model for the task).
- Provider cost estimator before running.

### Provider Adapter Interface

```python
class BaseProviderAdapter(ABC):
    @abstractmethod
    async def generate(
        self, prompt: str, config: ProviderConfig
    ) -> ProviderResponse: ...

    @abstractmethod
    async def generate_stream(
        self, prompt: str, config: ProviderConfig
    ) -> AsyncIterator[ProviderChunk]: ...

    @abstractmethod
    def metadata(self) -> ProviderMetadata: ...
```

---

## Reporting Module (`domain/reports/`)

**Purpose:** Aggregate, visualize, and export evaluation results.

**Responsibilities:**
- Execute aggregate queries across evaluation runs, tasks, and metrics.
- Build comparison reports (side-by-side model performance).
- Build trend reports (metric score over time).
- Build summary reports (overall pass/fail, cost summary).
- Export to CSV and JSON.
- Cache expensive report queries with configurable TTL.

**Inputs:** Report configuration (type, filters, time range, group-by).

**Outputs:** Structured report data, file downloads.

**Dependencies:** Evaluation module, Metrics module, `core/database.py`.

**Future extensions:**
- Scheduled report generation and email delivery.
- Custom report builder with drag-and-drop metric tiles.
- PDF export with embedded charts.

---

## Webhooks Module (`domain/webhooks/`)

**Purpose:** Outbound event notifications.

**Responsibilities:**
- Manage webhook endpoint configurations.
- Dispatch events to registered URLs with HMAC-SHA256 signatures.
- Retry with exponential backoff (up to 3 attempts).
- Track delivery status and log failures.

**Inputs:** Internal events (evaluation_run.completed, threshold.breached, campaign.completed).

**Outputs:** HTTP POST requests to configured endpoints.

**Dependencies:** `core/database.py`.

**Future extensions:**
- Event filtering (only send specific metric breaches).
- Webhook secret rotation.

---

## Dashboard Module (`domain/dashboard/`)

**Purpose:** Lightweight aggregation layer for frontend dashboard widgets.

**Responsibilities:**
- Compute aggregate statistics (total runs, pass rate, average scores, total cost).
- Compute time-series trends for charting.
- Compute comparison data for side-by-side run views.

**Inputs:** Project ID, filter parameters.

**Outputs:** Aggregated JSON responses.

**Dependencies:** Evaluation, Metrics, Reports modules.

**Future extensions:**
- Custom dashboard layouts that users can configure.
- Saved dashboard presets.
- Embeddable dashboard iframes.

---

## Workers (`workers/`)

**Purpose:** Temporal Activity implementations — the executable units of work called by Workflows.

### Evaluation Activities

- `resolve_configuration` — Load experiment/profile/prompt/dataset configuration, validate, return resolved config.
- `execute_prompt` — Call a single provider model with a single prompt. Record raw response, latency, tokens, cost.
- `compute_metric` — Run a single metric against a single evaluation task using the appropriate evaluator adapter.
- `aggregate_results` — Aggregate all metric results into run-level summaries, evaluate thresholds.
- `publish_events` — Publish domain events to the Event Bus after workflow milestones.

### Red Team Activities

- `generate_adversarial_variations` — Transform benign prompts into adversarial variants.
- `execute_probe` — Send a single adversarial probe to the target model.
- `classify_finding` — Evaluate probe response and classify severity.

### Export Activities

- `query_report_data` — Execute aggregate query for export.
- `generate_file` — Build CSV/JSON/PDF file.
- `upload_to_storage` — Upload to S3/local storage.
- `notify_completion` — Publish export-ready event.

### Design Rule

Every Activity is **idempotent**. Temporal may retry an Activity on worker failure; the Activity must produce the same result if called with the same input, even if previous attempts partially completed. This is achieved by:
- Checking for existing records before creating (upsert semantics).
- Using deterministic ID generation (UUID derived from input content).
- Avoiding side effects that cannot be rolled back.

---

## Infrastructure (`infrastructure/`)

### Temporal Client & Worker (`infrastructure/temporal/`)

- `client.py` — Temporal client connection, workflow start helpers, workflow stub cache.
- `worker.py` — Temporal worker process that registers all Activity implementations and starts listening.
- `converters/` — Custom data converters for passing complex types (Pydantic models) between workflows and activities.

Temporal Server runs as a separate process (or Docker container) with its own PostgreSQL database for workflow state persistence. In development, Temporal's dev server is used (single binary, no dependencies).

### Provider Adapters (`app/providers/`)

Concrete implementations of the provider adapter contract currently shipped:
- `openai/` — OpenAI-compatible SDK adapter (client, mappers, streaming, token usage, health).
- `anthropic/` — Anthropic SDK adapter (client, mappers, streaming, token usage, health).

Each provider adapter declares its available models via the Model Catalog (data, not code);
models can be added/updated without changing the adapter.

> **Planned (not yet implemented):** Additional providers (Gemini, Ollama, Groq, OpenRouter,
> Cohere, Mistral, Together AI) are roadmap Phase 11 work. Adding a provider requires a new
> adapter module registered with the provider registry, not just catalog entries — see
> `docs/ROADMAP.md` (Phase 11) and the provider extension point in
> `docs/evaluation/EVALUATION_ENGINE.md`.

### Evaluator Adapters (`infrastructure/evaluators/`)

Concrete implementations of `BaseEvaluatorAdapter`:
- `deepeval_adapter.py` — Wraps DeepEval metrics. Translates between RedOps Eval's `MetricInputs` schema and DeepEval's expected parameters.
- `ragas_adapter.py` — Wraps RAGAS metrics for retrieval-augmented generation evaluation.
- `custom_adapter.py` — Executes user-provided evaluation function via plugin interface.

The EvaluatorRegistry at startup scans all adapters and builds a routing table from metric name → adapter. When Evaluation Engine requests a metric computation, it passes the metric + inputs to the registry, which dispatches to the correct adapter.

### Event Bus (`infrastructure/event_bus/`)

- `redis_streams.py` — Production implementation using Redis Streams with consumer groups.
- `in_memory.py` — Testing implementation (synchronous publish, no persistence, inspectable event log).

### Storage (`infrastructure/storage/`)

Abstracts file storage behind a `StorageBackend` interface. Default implementation is local filesystem. S3/GCS implementations can be added without changing domain code.
