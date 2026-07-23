# RedOps Eval — Roadmap

## Phase 0: Project Bootstrap (Weeks 1–2)

**Complexity:** Low

**Goals:**
- Establish repository structure, tooling, and development environment.
- Make the project runnable with a single command for contributors.

**Deliverables:**
- Monorepo scaffold with `backend/` and `frontend/` directories.
- `pyproject.toml` with FastAPI, SQLAlchemy, Alembic, Temporal SDK, pytest, ruff.
- `package.json` with Vite, React, TypeScript, Tailwind, shadcn/ui.
- `docker-compose.yml` with PostgreSQL, Redis, Temporal Server, Temporal Admin, and the app.
- Pre-commit hooks (ruff, prettier, type checking).
- `CONTRIBUTING.md`, `README.md`, `LICENSE`.

**Dependencies:** None.

---

## Phase 1: Core Domain Models & API (Weeks 3–5)

**Complexity:** Medium

**Goals:**
- Implement the database schema and data access layer.
- Build the REST API for projects, prompts, datasets, and evaluations.
- Implement JWT authentication.

**Deliverables:**
- SQLAlchemy models for all entities (see DATABASE.md).
- Alembic migration scripts.
- REST API endpoints for:
  - `POST/GET/PUT/DELETE /projects`
  - `POST/GET/PUT/DELETE /prompts`
  - `POST/GET/DELETE /datasets`
  - `POST/GET /evaluations`
- Authentication module: register, login, token refresh.
- Unit tests for all services (80%+ coverage target on service layer).
- API documentation auto-generated via FastAPI (OpenAPI/Swagger).

**Dependencies:** Phase 0.

---

## Phase 2: Provider Abstraction + Model Catalog (Weeks 6–7)

**Complexity:** Medium

**Goals:**
- Design and implement the provider adapter interface.
- Build adapters for OpenAI, Anthropic, Gemini, and Ollama.
- Implement provider registry and credential management.
- Introduce the Model Catalog — separate providers from models with capabilities, pricing, rate limits, and context window.

**Deliverables:**
- `BaseProviderAdapter` abstract class + `ProviderRegistry`.
- `OpenAIAdapter`, `AnthropicAdapter`, `GeminiAdapter`, `OllamaAdapter`.
- `ProviderModel` database entity (Model Catalog).
- Capability-based model filtering.
- Cost calculator using per-model pricing data.
- Provider credential encryption at rest (AES-256-GCM).
- Provider health-check endpoint.
- Integration tests against provider mock servers.
- Provider comparison table in the UI.

**Key architectural change:** Providers and models are now separate entities. The Model Catalog is data-driven — adding a new model to an existing provider requires a database insert, not code changes.

**Dependencies:** Phase 1.

---

## Phase 3: Temporal, Evaluator Abstraction & Core Engine (Weeks 8–12)

**Complexity:** High

**Goals:**
- Introduce Temporal as the durable workflow orchestration layer.
- Build the Evaluator Abstraction Layer (decouple metrics from DeepEval).
- Implement core metrics: hallucination, faithfulness, answer relevancy, context precision, context recall.
- WebSocket progress streaming via Event Bus.

**Deliverables:**
- Temporal Server + Worker setup in Docker Compose.
- `EvaluationWorkflow` definition (evaluation orchestration as a Temporal workflow).
- Metric computation Temporal Activities.
- `BaseEvaluatorAdapter` interface + `DeepEvalAdapter` implementation.
- `DeepEvalAdapter` wrapping hallucination, faithfulness, answer relevancy, context precision, context recall.
- `MetricRegistry` for metric discovery and versioning.
- Event Bus foundation (Redis Streams implementation, in-memory for tests).
- Event: `TaskCompleted` → Redis pub/sub → WebSocket → UI.
- Threshold configuration and breach detection.
- `EvaluationRun` entity (workflow state managed by Temporal, not application code).
- Integration tests with real provider calls (limited, cost-controlled).

**Key architectural change:** Celery is replaced by Temporal. DeepEval is wrapped behind EvaluatorAdapter. No domain code imports DeepEval directly.

**Dependencies:** Phase 1, Phase 2.

---

## Phase 4: Safety & Red Teaming Metrics (Weeks 13–15)

**Complexity:** High

**Goals:**
- Implement toxicity, bias, prompt injection, and jailbreak detection.
- Build the Red Team campaign engine as a Temporal workflow.
- Create adversarial dataset templates.

**Deliverables:**
- Toxicity metric plugin (via EvaluatorAdapter).
- Bias metric plugin (demographic and stereotyping probes).
- Prompt injection resistance scorer (heuristic + LLM-based).
- Jailbreak resistance scorer (synthesized adversarial prompts).
- Red Team Engine:
  - Campaign configuration (dataset + metrics + model target).
  - `RedTeamWorkflow` (Temporal workflow for scheduled campaign execution).
  - Findings triage view.
  - Events: `FindingDetected`, `CampaignCompleted`.
- Pre-built adversarial dataset pack (OWASP LLM Top 10 aligned).

**Key architectural change:** Red Team campaigns use Temporal cron workflows (replaces Celery Beat). Findings are published as events, not stored via direct service calls.

**Dependencies:** Phase 3.

---

## Phase 5: Event Bus & Side-Effect Workers (Weeks 16–17)

**Complexity:** Medium

**Goals:**
- Fully operational Event Bus with all domain events wired.
- Implement webhook delivery, audit logging, and report refresh as event subscribers.
- Add the Event Log database table for debugging and distributed tracing.

**Deliverables:**
- All domain events defined and published from their respective contexts:
  - EvaluationStarted, EvaluationCompleted, MetricComputed, TaskCompleted.
  - ThresholdBreached, FindingDetected, CampaignCompleted.
  - DatasetUploaded, PromptVersionCreated, ProviderConnected.
- Event subscribers:
  - Webhook delivery worker.
  - Audit log writer.
  - Report refresh trigger.
  - Notification service (email/Slack — basic implementation).
- Event Log API endpoint for querying/debugging.
- Correlation ID propagation across event chains.
- Dead-letter queue monitoring.

**Dependencies:** Phase 3.

---

## Phase 6: Experiments, Profiles & Reporting (Weeks 18–21)

**Complexity:** Medium

**Goals:**
- Introduce the Experiment hierarchy (Project → Experiment → EvaluationRun).
- Build the Profile system (reusable evaluation configuration templates).
- Build the reporting and dashboard module.
- Implement cost tracking and token usage analytics.

**Deliverables:**
- Experiment entity + API + UI.
- Profile entity + API + UI (Quick, Safety, RAG, Cost, Regression, Production Gate).
- Dashboard UI with:
  - Project overview cards.
  - Recent evaluation run timeline.
  - Cost/latency trend charts (Recharts).
- Report Service:
  - Side-by-side model comparison reports.
  - Experiment comparison (delta from baseline).
  - Metric distribution histograms.
  - Pass/fail summary by threshold.
- Export Workflow (Temporal — handles large exports without HTTP timeout).
- Latency percentile tracking (p50, p95, p99).
- Cost aggregation per model per project per time window.

**Key architectural change:** The new hierarchy `Project → Experiment → EvaluationRun` replaces the flat `Project → EvaluationRun` model. Backward compatibility is maintained via nullable `experiment_id`.

**Dependencies:** Phase 3, Phase 4, Phase 5.

---

## Phase 7: Metrics Plugin System (Weeks 22–23)

**Complexity:** Medium

**Goals:**
- Formalize the metrics plugin architecture.
- Enable third-party metric discovery via Python entry points.
- Build the plugin development toolkit.

**Deliverables:**
- `BaseMetric` abstract class with full metadata (version, category, required inputs, evaluator type).
- `MetricRegistry` with plugin discovery (`importlib.metadata.entry_points`).
- Plugin packaging documentation and cookiecutter template.
- RAGASAdapter for the Evaluator layer.
- Composite metric support (average, weighted, custom aggregation).
- Metric versioning — results stored with metric_definition_id referencing the exact metric version used.

**Dependencies:** Phase 3 (Evaluator Abstraction), Phase 6 (reporting for metric version visualization).

---

## Phase 8: Frontend Completion (Weeks 24–26)

**Complexity:** Medium

**Goals:**
- Complete all UI views.
- Polish user experience, responsiveness, error states.
- Implement dark mode.

**Deliverables:**
- Full CRUD UI for all domain objects.
- Evaluation run configuration wizard with profile selection.
- Experiment management UI with comparison view.
- Dataset upload with preview and validation.
- Red Team campaign management UI.
- Settings pages: provider credentials, Models, webhooks, API keys, team management.
- Dark mode toggle (persisted).
- Responsive layout (mobile sidebar collapse).
- Loading skeletons, error boundaries, toast notifications.

**Dependencies:** Phase 1–7 (all API endpoints).

---

## Phase 9: CI/CD, Security & Hardening (Weeks 27–28)

**Complexity:** Medium

**Goals:**
- Harden the application for production use.
- Build the CI/CD evaluation gate.
- Security audit and penetration test preparation.

**Deliverables:**
- GitHub Actions workflows:
  - `ci.yml` — lint, type-check, test (backend + frontend).
  - `docker-build.yml` — build and push images.
  - `release.yml` — semantic release, changelog generation.
- Evaluation Gate CLI (`redops-gate`):
  - CLI tool to trigger an evaluation run and block on threshold breach.
  - GitHub Action wrapper and GitLab CI template.
  - Idempotency key support for safe CI/CD retries.
- Rate limiting middleware (configurable per route).
- Input sanitization and XSS/CSRF protection audit.
- Dependency vulnerability scanning (`pip audit`, `npm audit`).
- Secrets scanning in CI.

**Dependencies:** Phase 6, Phase 8.

---

## Phase 10: Public Release & Community (Weeks 29–30)

**Complexity:** Low

**Goals:**
- Launch on GitHub as a public repository.
- Onboard early adopters and contributors.

**Deliverables:**
- Public GitHub repository with issues enabled.
- GitHub Discussions or Discord server.
- Contributor onboarding guide and good-first-issue labels.
- Project website / documentation site (GitHub Pages or Vercel).
- Blog post / launch announcement.
- First community contribution merged.

**Dependencies:** Phase 9.

---

## Phase 11: Post-Launch (Ongoing)

**Goals:**
- Additional providers (Groq, OpenRouter, Cohere, Mistral, Together AI) — model catalog entries, no code changes needed.
- Additional metrics via community plugins.
- Multi-modal evaluation (vision, audio) — Interaction.type = "multi_modal", capability-based filtering.
- Agent evaluation workflows (Interaction.type = "agent", tool-calling activities).
- MCP Server integration (tool providers as MCP adapters).
- Multi-agent system evaluation (agent topology workflows).
- Long-context evaluation (context window segmentation, recall degradation measurement).
- RAG evaluation (retrieval quality metrics via RAGASAdapter).
- On-prem Helm chart for Kubernetes deployment.
- SSO / OAuth2 enterprise authentication.
- Performance optimization (Temporal worker auto-scaling, result caching).
