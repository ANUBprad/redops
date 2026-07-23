# RedOps Eval — API Specification

## Design Conventions

- Base URL: `/api/v1`
- Authentication: Bearer JWT token in `Authorization` header (or API key in `X-API-Key` header).
- Pagination: All list endpoints accept `?page=1&page_size=50` (default page_size=20, max 100).
- Sorting: `?sort_by=created_at&sort_order=desc`.
- Filtering: `?field=value`. Complex filters use a JSON-encoded `filter` parameter.
- Responses: Standard envelope: `{"data": ..., "meta": {"page": ..., "page_size": ..., "total": ...}}`.
- Errors: `{"error": {"code": "VALIDATION_ERROR", "message": "...", "details": [...]}}`.
- Links: HATEOAS-inspired `links` object included in single-resource responses.
- API versioning: Via URL prefix (`/api/v1/`). Version is bumped only on backward-incompatible changes. Additionally, a `Accept-Version` header can be used for content negotiation within a major version (e.g., `Accept-Version: 1.2`).
- Rate limits: 1000 req/min per team (default), configurable. Returned via `X-RateLimit-*` headers.
- Long-running operations: Endpoints that trigger background work (evaluation runs, exports) return `202 Accepted` with a `Location` header pointing to the resource and a `workflow_id` field referencing the Temporal workflow execution. Clients poll the resource endpoint or subscribe via WebSocket for completion.
- Idempotency: Mutating endpoints accept an `Idempotency-Key` header. If the same key is received within 24 hours, the previous response is returned (cached). This is critical for CI/CD pipeline safety.

---

## Authentication

### `POST /api/v1/auth/register`
Create a new user account. Returns a JWT and refresh token.

### `POST /api/v1/auth/login`
Authenticate with email/password. Returns JWT (access) and refresh token.

### `POST /api/v1/auth/refresh`
Exchange a refresh token for a new JWT.

### `POST /api/v1/auth/logout`
Invalidate the current refresh token (server-side blacklist).

### `GET /api/v1/auth/me`
Return the current user's profile and team memberships.

### `PUT /api/v1/auth/me`
Update the current user's profile (name, avatar, preferences).

### `POST /api/v1/auth/change-password`
Change the current user's password. Requires current password confirmation.

---

## API Keys

### `GET /api/v1/api-keys`
List API keys for the authenticated team.

### `POST /api/v1/api-keys`
Create a new API key. The raw key is returned in the response (shown once).

### `DELETE /api/v1/api-keys/{key_id}`
Revoke an API key.

---

## Teams

### `GET /api/v1/teams`
List teams the current user belongs to.

### `POST /api/v1/teams`
Create a new team. The creator becomes the owner.

### `GET /api/v1/teams/{team_id}`
Get team details.

### `PUT /api/v1/teams/{team_id}`
Update team settings (name, billing info).

### `DELETE /api/v1/teams/{team_id}`
Soft-delete a team (owner only).

### `GET /api/v1/teams/{team_id}/members`
List team members with roles.

### `PUT /api/v1/teams/{team_id}/members/{user_id}`
Change a member's role.

### `DELETE /api/v1/teams/{team_id}/members/{user_id}`
Remove a member from the team.

---

## Projects

### `GET /api/v1/projects`
List projects within the authenticated team. Supports `?search=` query.

### `POST /api/v1/projects`
Create a new project. Body: `{name, description, tags?}`.

### `GET /api/v1/projects/{project_id}`
Get project details, including summary stats (total runs, last run date, pass rate).

### `PUT /api/v1/projects/{project_id}`
Update project metadata.

### `DELETE /api/v1/projects/{project_id}`
Soft-delete a project.

---

## Prompts

### `GET /api/v1/projects/{project_id}/prompts`
List prompts in a project.

### `POST /api/v1/projects/{project_id}/prompts`
Create a new prompt. Body: `{name, template, variables, commit_message?}`.

### `GET /api/v1/projects/{project_id}/prompts/{prompt_id}`
Get prompt details and current version.

### `PUT /api/v1/projects/{project_id}/prompts/{prompt_id}`
Update the prompt (creates a new version).

### `DELETE /api/v1/projects/{project_id}/prompts/{prompt_id}`
Soft-delete a prompt.

### `GET /api/v1/projects/{project_id}/prompts/{prompt_id}/versions`
List all versions of a prompt.

### `GET /api/v1/projects/{project_id}/prompts/{prompt_id}/versions/{version_id}`
Get a specific prompt version with the template snapshot.

---

## Datasets

### `GET /api/v1/projects/{project_id}/datasets`
List datasets.

### `POST /api/v1/projects/{project_id}/datasets`
Create a dataset. Supports:
- `Content-Type: application/json` with rows inline.
- `Content-Type: multipart/form-data` with a CSV/JSONL file upload.

Body/Form: `{name, description, file?, rows?}`.

### `GET /api/v1/projects/{project_id}/datasets/{dataset_id}`
Get dataset metadata.

### `PUT /api/v1/projects/{project_id}/datasets/{dataset_id}`
Update dataset metadata (creates new version only if rows change).

### `DELETE /api/v1/projects/{project_id}/datasets/{dataset_id}`
Soft-delete a dataset.

### `GET /api/v1/projects/{project_id}/datasets/{dataset_id}/versions`
List dataset versions.

### `GET /api/v1/projects/{project_id}/datasets/{dataset_id}/versions/{version_id}/rows`
Paginated row retrieval. Supports `?offset=0&limit=100`.

---

## Provider Settings

### `GET /api/v1/projects/{project_id}/providers`
List configured providers for a project (returns provider names, never API keys).

### `POST /api/v1/projects/{project_id}/providers`
Add/configure a provider. Body: `{provider_name, config, encrypted_api_key?}`.

### `PUT /api/v1/projects/{project_id}/providers/{provider_name}`
Update provider configuration. Re-encrypts the API key if provided.

### `DELETE /api/v1/projects/{project_id}/providers/{provider_name}`
Remove a provider configuration.

### `POST /api/v1/projects/{project_id}/providers/{provider_name}/test`
Send a test prompt to verify connectivity. Returns the response, latency, and token count without persisting anything.

### `GET /api/v1/providers/available`
Return a list of all supported providers (no auth required). Used for UI dropdowns.

---

## Provider Models

### `GET /api/v1/providers/{provider_name}/models`
List available models for a provider (from the Model Catalog). Returns model name, capabilities, pricing, rate limits, context window.

### `GET /api/v1/providers/models?capabilities=vision,tool_calling`
Query models by capability. Returns all models across providers that match the required capabilities.

### `GET /api/v1/projects/{project_id}/providers/models`
List models available to a project (intersection of configured providers + their active models).

---

## Experiments

### `GET /api/v1/projects/{project_id}/experiments`
List experiments. Supports filters: `?status=active&tags=regression`.

### `POST /api/v1/projects/{project_id}/experiments`
Create a new experiment. Body: `{name, description?, hypothesis?, baseline_run_id?, tags?}`.

### `GET /api/v1/projects/{project_id}/experiments/{experiment_id}`
Get experiment details, including linked run count, status, and baseline comparison summary.

### `PUT /api/v1/projects/{project_id}/experiments/{experiment_id}`
Update experiment metadata, conclusion, or status.

### `DELETE /api/v1/projects/{project_id}/experiments/{experiment_id}`
Soft-delete an experiment (cancels associated pending runs).

### `GET /api/v1/projects/{project_id}/experiments/{experiment_id}/runs`
List evaluation runs within an experiment. Supports standard pagination and filtering.

### `POST /api/v1/projects/{project_id}/experiments/{experiment_id}/runs`
Trigger a new evaluation run within this experiment. Same body as evaluation run creation, with experiment_id implied.

### `GET /api/v1/projects/{project_id}/experiments/{experiment_id}/comparison`
Return side-by-side comparison of all runs in the experiment. Shows metric scores per run per model, with delta from baseline.

---

## Evaluation Profiles

### `GET /api/v1/projects/{project_id}/profiles`
List evaluation profiles. Includes built-in system profiles and project-custom profiles.

### `POST /api/v1/projects/{project_id}/profiles`
Create a custom profile. Body: `{name, description, extends? (parent profile name), configuration: {...}}`.

### `GET /api/v1/projects/{project_id}/profiles/{profile_id}`
Get profile details and resolved configuration.

### `PUT /api/v1/projects/{project_id}/profiles/{profile_id}`
Update a custom profile. System profiles are read-only.

### `DELETE /api/v1/projects/{project_id}/profiles/{profile_id}`
Delete a custom profile. System profiles cannot be deleted.

### `POST /api/v1/projects/{project_id}/profiles/{profile_id}/preview`
Preview the resolved configuration for a profile (useful for understanding inherited settings before running).

---

## Evaluation Runs

### `GET /api/v1/projects/{project_id}/evaluations`
List evaluation runs. Supports filters: `?status=completed&metrics=hallucination,toxicity&experiment_id=uuid`.

### `POST /api/v1/projects/{project_id}/evaluations`
Create and trigger a new evaluation run. Body:
```json
{
  "name": "GPT-4 vs Claude Hallucination",
  "experiment_id": "uuid (optional, for grouping)",
  "profile_id": "uuid (optional, overrides inline config)",
  "prompt_version_id": "uuid",
  "dataset_version_id": "uuid",
  "providers": [
    {"provider": "openai", "model": "gpt-4o"},
    {"provider": "anthropic", "model": "claude-3-opus"}
  ],
  "metrics": ["hallucination", "faithfulness", "answer_relevancy"],
  "thresholds": {"hallucination": {"lte": 0.3}},
  "webhook_url": "https://..."
}
```
Returns `202 Accepted` with `{run_id, workflow_id, status: "pending"}`. The run executes asynchronously via Temporal.

### `GET /api/v1/projects/{project_id}/evaluations/{run_id}`
Get evaluation run status and summary (aggregate scores per metric per provider).

### `DELETE /api/v1/projects/{project_id}/evaluations/{run_id}`
Cancel a running evaluation (sends cancellation signal to Temporal workflow) or soft-delete a completed one.

## Evaluation Runs

### `GET /api/v1/projects/{project_id}/evaluations`
List evaluation runs. Supports filters: `?status=completed&metrics=hallucination,toxicity`.

### `POST /api/v1/projects/{project_id}/evaluations`
Create and trigger a new evaluation run. Body:
```json
{
  "name": "GPT-4 vs Claude Hallucination",
  "prompt_version_id": "uuid",
  "dataset_version_id": "uuid",
  "providers": ["openai/gpt-4", "anthropic/claude-3-opus"],
  "metrics": ["hallucination", "faithfulness", "answer_relevancy"],
  "thresholds": {"hallucination": {"lte": 0.3}},
  "webhook_url": "https://..."
}
```
Returns the evaluation run ID. The run executes asynchronously.

### `GET /api/v1/projects/{project_id}/evaluations/{run_id}`
Get evaluation run status and summary (aggregate scores per metric per provider).

### `DELETE /api/v1/projects/{project_id}/evaluations/{run_id}`
Cancel a running evaluation or soft-delete a completed one.

### `GET /api/v1/projects/{project_id}/evaluations/{run_id}/tasks`
List individual evaluation tasks (one per prompt row per provider). Supports pagination.

### `GET /api/v1/projects/{project_id}/evaluations/{run_id}/tasks/{task_id}`
Get a single task with full input, output, latency, token count, cost, and metric results.

### `GET /api/v1/projects/{project_id}/evaluations/{run_id}/tasks/{task_id}/metrics`
List metric results for a single task.

---

## WebSocket: Evaluation Progress

### `WS /api/v1/ws/evaluations/{run_id}`
Subscribe to real-time progress updates for an evaluation run. Messages:
```json
{
  "type": "task_completed",
  "task_id": "uuid",
  "provider": "openai/gpt-4",
  "row_index": 42,
  "progress": {"completed": 42, "total": 100}
}
```
```json
{
  "type": "run_completed",
  "run_id": "uuid",
  "summary": { "overall_pass": true }
}
```
```json
{
  "type": "error",
  "task_id": "uuid",
  "message": "Rate limit exceeded"
}
```

---

## Metrics & Metric Definitions

### `GET /api/v1/metrics`
Return the list of all available metrics from the MetricRegistry. Each entry includes: name, display_name, description, category, evaluator_type, required_inputs, version, and metadata.

### `GET /api/v1/metrics/{metric_name}`
Get details for a specific metric, including version history if applicable.

### `GET /api/v1/projects/{project_id}/metrics/thresholds`
List threshold configurations for the project.

### `PUT /api/v1/projects/{project_id}/metrics/thresholds`
Bulk update threshold configurations. Body: `[{"metric_name": "hallucination", "comparison": "lte", "value": 0.2, "severity": "critical"}, ...]`.

---

## Workflow Executions

### `GET /api/v1/workflows`
List Temporal workflow executions. Supports filters: `?status=running&type=evaluation`. For operators and debugging.

### `GET /api/v1/workflows/{workflow_id}`
Get workflow execution details, including status, start/completion time, and error details. Links to Temporal Web UI if configured.

### `POST /api/v1/workflows/{workflow_id}/cancel`
Request cancellation of a running workflow.

---

## Event Log

### `GET /api/v1/events`
Query domain events. Supports filters: `?event_type=EvaluationCompleted&entity_type=evaluation_run&entity_id=uuid&from=ISO&to=ISO`. Paginated. For auditing and debugging.

### `GET /api/v1/events/{event_id}`
Get a single event with full payload and processing metadata (which subscribers processed it, when).

### `GET /api/v1/events/correlated/{correlation_id}`
Get all events sharing a correlation ID. Enables distributed tracing across publisher → subscriber chains.

---

## Red Team Campaigns

### `GET /api/v1/projects/{project_id}/red-team/campaigns`
List campaigns.

### `POST /api/v1/projects/{project_id}/red-team/campaigns`
Create a campaign. Body: `{name, target_provider, target_model, strategy, adversarial_dataset_id, schedule?}`.

### `GET /api/v1/projects/{project_id}/red-team/campaigns/{campaign_id}`
Get campaign details and summary statistics.

### `PUT /api/v1/projects/{project_id}/red-team/campaigns/{campaign_id}`
Update campaign configuration.

### `POST /api/v1/projects/{project_id}/red-team/campaigns/{campaign_id}/run`
Trigger a campaign execution immediately.

### `GET /api/v1/projects/{project_id}/red-team/campaigns/{campaign_id}/findings`
List findings from this campaign, optionally filtered by severity.

### `PUT /api/v1/projects/{project_id}/red-team/campaigns/{campaign_id}/findings/{finding_id}`
Triage a finding (mark as reviewed, dismiss, assign).

---

## Reports

### `GET /api/v1/projects/{project_id}/reports`
List saved reports.

### `POST /api/v1/projects/{project_id}/reports`
Create a new report configuration. Body: `{name, type, configuration: {...}}`.

### `GET /api/v1/projects/{project_id}/reports/{report_id}`
Get report data (executes the report query and returns results).

### `PUT /api/v1/projects/{project_id}/reports/{report_id}`
Update report configuration.

### `DELETE /api/v1/projects/{project_id}/reports/{report_id}`
Delete a report configuration.

### `GET /api/v1/projects/{project_id}/reports/{report_id}/export`
Export report data. Query param `?format=csv|json`. Returns a file download.

---

## Dashboard / Aggregations

### `GET /api/v1/projects/{project_id}/dashboard/summary`
Return aggregate statistics for the project dashboard:
- Total runs (last 30 days)
- Pass/fail counts
- Average scores per metric
- Total cost (last 30 days)
- Average latency per provider

### `GET /api/v1/projects/{project_id}/dashboard/trends?metric=hallucination&interval=day&days=30`
Time-series data for charting.

### `GET /api/v1/projects/{project_id}/dashboard/comparison?run_ids=uuid1,uuid2`
Side-by-side metric comparison of two or more evaluation runs.

---

## Webhooks

### `GET /api/v1/teams/{team_id}/webhooks`
List configured webhooks.

### `POST /api/v1/teams/{team_id}/webhooks`
Create a webhook. Body: `{url, events: [...], secret?}`.

### `PUT /api/v1/teams/{team_id}/webhooks/{webhook_id}`
Update webhook configuration.

### `DELETE /api/v1/teams/{team_id}/webhooks/{webhook_id}`
Delete a webhook.

### `POST /api/v1/teams/{team_id}/webhooks/{webhook_id}/test`
Send a test event to verify the endpoint.

---

## Auditing

### `GET /api/v1/teams/{team_id}/audit-log`
List audit log entries. Supports filters: `?actor_id=&action=&resource_type=&from=&to=`. Paginated.

---

## Health & System

### `GET /api/v1/health`
Simple health check (returns `{"status": "ok"}`).

### `GET /api/v1/health/ready`
Readiness check (verifies DB connection, Redis connection, Temporal Server health, and at least one Temporal worker connected).

### `GET /api/v1/version`
Return the current application version and commit SHA.

### `GET /api/v1/system/dependencies`
Return the status of all system dependencies (PostgreSQL, Redis, Temporal Server, Temporal Workers) with latency. For operational dashboards.
