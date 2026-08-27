# RedOps Eval — Database Design

## Design Philosophy

- **Append-mostly**: Evaluation runs and metric results are immutable once written. There is no UPDATE path for completed evaluations. This creates a complete audit trail.
- **Relational core, JSONB edges**: Entities with stable schemas (projects, users, prompts) use strict relational columns. Entities with variable schemas (metric configurations, provider settings) use JSONB columns for flexibility.
- **Identity as UUIDv7**: All primary keys use UUIDv7, which is time-sortable and prevents ID enumeration attacks while avoiding the fragmentation of UUIDv4 in B-tree indexes.
- **Soft deletes**: Projects, datasets, and prompts use a `deleted_at` timestamp column. Hard deletes are never issued. This protects against accidental data loss.
- **Temporal versioning**: Prompts and datasets are versioned. Every update creates a new version row; the previous version remains accessible.

## Entities

The database consists of the following entity groups:

### Core
- User
- Team
- Project

### Configuration
- Prompt (with PromptVersion)
- Dataset (with DatasetVersion, DatasetRow)
- EvaluationProfile
- ProviderModel

### Experimentation
- Experiment

### Evaluation
- EvaluationRun
- EvaluationTask
- MetricResult
- MetricDefinition

### Red Teaming
- RedTeamCampaign
- RedTeamFinding

### Reporting & Analytics
- Report
- MetricThreshold

### Workflow & Events
- WorkflowExecution
- EventLog

### Auth & Audit
- ApiKey
- AuditLog
- Webhook

---

## Table Descriptions

### `users`
Stores authenticated users. Supports email/password (hashed with bcrypt) and external OAuth identities JSONB column. Each user belongs to one or more teams via a join table.

### `teams`
Organizational unit for multi-tenant isolation. Every resource (projects, datasets, API keys) is scoped to a team. A user can belong to multiple teams with role-based access (owner, admin, member, viewer).

### `teams_users`
Join table linking users to teams. Includes a `role` column (ENUM: owner, admin, member, viewer) and `joined_at` timestamp.

### `projects`
Top-level organizational container. A project has a name, description, optional tags (JSONB array), and belongs to exactly one team. Evaluation runs, prompts, datasets, and reports are scoped to a project.

### `prompts`
Stores prompt templates with variable placeholders (e.g., `{{context}}`, `{{question}}`). The `template` column stores the template string. Variables are stored as a JSONB array of variable names.

### `prompt_versions`
Every update to a prompt creates a new version row. Columns: `version_number` (incrementing integer), `template` (snapshot), `variables` (snapshot), `commit_message`, `created_by` (FK to user). The prompt's `current_version_id` FK points here.

### `datasets`
Metadata about an evaluation dataset. Has a name, description, row count, column schema (JSONB: `{"columns": [{"name": "input", "type": "string"}, ...]}`), and source type (uploaded, generated, imported).

### `dataset_versions`
Like prompt_versions — every dataset update creates a new version. Stores the file path to the raw data (if uploaded), or references the DatasetRows table. Also stores row count and a checksum for integrity verification.

### `dataset_rows`
Individual rows within a dataset version. Each row is a JSONB document (`{"input": "...", "expected_output": "...", "context": "..."}`). Indexed by dataset_version_id. Large datasets live in this table; the raw uploaded file is archived in blob storage (S3/GCS) with a reference in `dataset_versions.storage_path`.

### `provider_settings`
Stores encrypted credentials and configuration for each LLM provider per team/project. Columns: `team_id`, `project_id` (nullable — global or project-scoped), `provider_name` (enum, currently supports the implemented `openai`, `anthropic`, and `groq` adapters; the planned set also includes `gemini`, `ollama`, `openrouter` per Phase 11), `config` (JSONB: endpoint URL, default parameters, etc.), `encrypted_api_key` (AES-256-GCM). The raw key is never logged or returned in API responses. This table stores *provider-level* settings only; *model-level* settings live in `provider_models`.

### `provider_models`
New table separating models from providers. Each provider exposes zero or more models. Columns: `provider_settings_id` (FK), `model_name` (gpt-4o, claude-3-opus, gemini-1.5-pro), `display_name`, `capabilities` (JSONB array: ["text", "vision", "audio", "tool_calling", "streaming"]), `pricing` (JSONB: `{"input_per_million_tokens": 2.50, "output_per_million_tokens": 10.00, "per_request": 0.0}`), `rate_limits` (JSONB: `{"rpm": 10000, "tpm": 200000, "max_concurrent": 50}`), `context_window` (integer, max tokens), `max_output_tokens` (integer), `metadata` (JSONB: release date, deprecation status, documentation URL), `is_default` (boolean, per provider), `is_deprecated` (boolean). This enables the Model Catalog to be data-driven.

### `evaluation_profiles`
Reusable configuration templates. Columns: `project_id`, `name`, `description`, `scope` (enum: system, project, custom), `configuration` (JSONB: `{"metrics": ["hallucination", ...], "thresholds": {"hallucination": {"lte": 0.3}}, "concurrency": 10, "timeout_seconds": 300, "evaluator_model": "gpt-4o"}`), `is_builtin` (boolean — system profiles cannot be deleted). Profiles define which metrics run, their thresholds, parallel execution limits, and the evaluator model.

### `experiments`
A hypothesis or question the user wants to answer by running evaluations. Columns: `project_id`, `name`, `description`, `hypothesis` (text, optional — e.g., "Claude 3.5 generates more factual summaries than GPT-4o"), `status` (draft, active, completed, archived), `baseline_run_id` (nullable FK to evaluation_run — the "control" for comparison), `conclusion` (text, nullable — recorded after analysis), `tags` (JSONB array). An experiment groups multiple evaluation runs for comparison.

### `evaluation_runs`
An evaluation run is a single execution of an evaluation suite. Columns: `status` (pending, running, completing, completed, failed, cancelled), `project_id`, `configuration` (JSONB: selected metrics, selected providers, prompt version ID, dataset version ID, threshold overrides), `started_at`, `completed_at`, `error_details` (JSONB for structured error reporting). This is the central fact table.

### `evaluation_tasks`
One row per (evaluation_run_id, dataset_row_id, provider_name). Represents a single prompt-completion pair. Columns: `status`, `prompt_text`, `response_text`, `latency_ms`, `token_count_prompt`, `token_count_completion`, `cost_usd`, `model_name`, `error_details`. Multiple metric results reference a single evaluation_task.

### `metric_definitions`
Registry of all available metrics (built-in and plugins). Columns: `name` (unique, e.g., "hallucination"), `display_name`, `description`, `category` (enum: safety, performance, cost, custom), `evaluator_type` (enum: deepeval, ragas, custom, heuristic), `required_inputs` (JSONB array: ["prompt", "response", "context", "ground_truth"]), `version` (string, semver), `plugin_module` (nullable string — Python module path for plugin metrics), `metadata` (JSONB: author, documentation URL, tags), `is_active` (boolean — can disable problematic metrics without removing). This table is populated at startup by the MetricRegistry from built-in metrics and discovered plugins.

### `metric_results`
One row per (evaluation_task_id, metric_definition_id). Immutable. Columns: `metric_definition_id` (FK to metric_definitions), `score` (float, normalized 0–1), `threshold` (nullable float, the threshold at time of evaluation), `passed` (boolean), `details` (JSONB: explanation, sub-scores, evaluator model info), `computed_at`. Indexed by evaluation_run_id for fast aggregation queries. References metric_definitions instead of a string metric_name for version traceability.

### `red_team_campaigns`
Configuration for an automated red-teaming campaign. Columns: `name`, `project_id`, `target_provider`, `target_model`, `strategy` (enum: prompt_injection, jailbreak, bias_probe, toxicity_probe), `adversarial_dataset_id` (FK to dataset), `schedule` (cron expression, nullable — for recurring campaigns), `status` (draft, active, completed, archived). Campaign execution creates evaluation_runs internally.

### `red_team_findings`
Results from a red team campaign that exceeded a severity threshold. Columns: `campaign_id`, `evaluation_task_id`, `severity` (low, medium, high, critical), `category`, `details` (JSONB), `triaged` (boolean), `triaged_by`, `triaged_at`.

### `reports`
Saved report configurations. A report defines a view over evaluation data. Columns: `project_id`, `name`, `type` (comparison, trend, summary), `configuration` (JSONB: metric filters, time range, model filter, provider filter, group-by), `created_by`.

### `metric_thresholds`
Configuration for threshold-based pass/fail on evaluation metrics. Columns: `project_id`, `metric_name`, `comparison` (gte, lte, inside_range), `value`, `severity` (warning, critical). When an evaluation run completes, thresholds are evaluated and can trigger webhooks.

### `api_keys`
API tokens for programmatic access. Columns: `team_id`, `name`, `key_hash` (SHA-256 of the raw key — the raw key is shown once at creation), `permissions` (JSONB array of allowed scopes), `expires_at`, `last_used_at`.

### `audit_log`
Append-only log of all state-changing operations. Columns: `actor_type` (user, api_key, system), `actor_id`, `action`, `resource_type`, `resource_id`, `details` (JSONB), `ip_address`, `user_agent`, `timestamp`. Retention is configurable (default 90 days).

### `webhooks`
Outbound webhook configurations. Columns: `team_id`, `url`, `secret` (for HMAC signing), `events` (JSONB array: evaluation_run.completed, threshold.breached, campaign.completed, metric.computed, experiment.completed), `retry_count`, `last_success_at`, `last_failure_at`.

### `workflow_executions`
Tracks Temporal workflow executions for observability and debugging. Columns: `workflow_id` (Temporal workflow ID), `run_id` (Temporal run ID, UUID), `workflow_type` (enum: evaluation, red_team, export, scheduled_eval, report_generation), `entity_type` (polymorphic: evaluation_run, red_team_campaign, etc.), `entity_id` (UUID of the entity), `status` (running, completed, failed, cancelled, timed_out), `started_at`, `completed_at`, `error_details` (JSONB), `temporal_history_url` (nullable link to Temporal Web UI). This is a read-only view for operators; Temporal is the source of truth, this table is a denormalized index for fast API queries.

### `event_log`
Append-only log of all domain events published to the Event Bus. Columns: `event_type` (EvaluationCompleted, MetricComputed, ProviderConnected, DatasetUploaded, PromptVersionCreated, ThresholdBreached, etc.), `entity_type`, `entity_id`, `payload` (JSONB — full event payload), `metadata` (JSONB: actor, source_ip, request_id, correlation_id), `published_at`, `processed_by` (JSONB array of subscriber names that acknowledged this event). Retention is configurable (default 30 days raw, 1 year aggregated). This serves as both an audit trail and a subscriber dead-letter debugging aid.

---

## Relationships

```
User N──M Team                          (via team_users)
Team 1──N Project
Project 1──N Experiment
Project 1──N EvaluationProfile
Experiment 1──N EvaluationRun
Project 1──N Prompt
Prompt 1──N PromptVersion
Project 1──N Dataset
Dataset 1──N DatasetVersion
DatasetVersion 1──N DatasetRow
Project 1──N ProviderSettings
ProviderSettings 1──N ProviderModel
Project 1──N EvaluationRun
EvaluationRun 1──N EvaluationTask
EvaluationTask 1──N MetricResult
MetricDefinition 1──N MetricResult
Project 1──N RedTeamCampaign
RedTeamCampaign 1──N RedTeamFinding
Project 1──N Report
Project 1──N MetricThreshold
Team 1──N ApiKey
Team 1──N Webhook
Entity 1──N WorkflowExecution       (polymorphic via entity_type + entity_id)
```

---

## Indexes

### Core Performance Indexes
- `evaluation_runs(project_id, created_at DESC)` — Default query: "show me recent runs for this project."
- `evaluation_tasks(evaluation_run_id)` — Fast task lookup for run detail views.
- `metric_results(evaluation_task_id)` — Fast metric lookup per task.

### Analytical Indexes
- `metric_results(metric_definition_id, computed_at)` — Time-series aggregation by metric.
- `evaluation_tasks(provider_name, model_name, created_at)` — Provider-specific cost/latency analysis.
- `evaluation_runs(project_id, status)` — "Show me currently running evaluations."
- `evaluation_runs(experiment_id)` — "Show me all runs in an experiment."

### Lookup Indexes
- `api_keys(key_hash)` — Fast API key lookup on every authenticated request.
- `audit_log(resource_type, resource_id, timestamp)` — Audit trail queries.
- `dataset_rows(dataset_version_id)` — Paginated row retrieval.
- `provider_models(provider_settings_id, is_deprecated)` — Active model listing.
- `workflow_executions(entity_type, entity_id)` — Workflow lookup by entity.
- `event_log(event_type, published_at)` — Event replay and debugging.
- `event_log(correlation_id)` — Distributed tracing across events.

### Partial Indexes
- `evaluation_runs WHERE deleted_at IS NULL` — Exclude soft-deleted runs from default queries.
- `projects WHERE deleted_at IS NULL`
- `prompts WHERE deleted_at IS NULL`

### Full-Text Search
- GIN index on `projects(name)` for project search.
- GIN index on `prompts(template)` for prompt template search.

---

## Migration Strategy

- Alembic handles all schema migrations.
- Migrations are forward-only. Rollbacks are tested in CI but used only in development.
- Zero-downtime migrations follow the expand-migrate-contract pattern:
  1. **Expand**: Add new columns/tables (application handles both old and new schema).
  2. **Migrate**: Backfill data in the background.
  3. **Contract**: Remove old columns (after confirming no reads).
- Large tables (`metric_results`, `audit_log`) use declarative partitioning by month at creation time to prevent future migration pain.

## Future Considerations

- **ClickHouse for analytics**: If metric result volume exceeds 100M rows/month, migrate `metric_results` to ClickHouse for columnar aggregation performance. The application layer abstracts writes behind a `MetricResultRepository` interface.
- **S3 for raw data**: Large dataset files (>10MB uploaded JSON/CSV) are stored in S3/GCS with only metadata in PostgreSQL. The `dataset_versions.storage_path` column references the object storage location.
- **Read replicas**: Report generation queries can be routed to a read replica once the primary write load warrants it.
