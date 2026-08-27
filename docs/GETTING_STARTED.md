# RedOps Eval — Getting Started

This guide takes a new user from zero to their first evaluation run in about ten minutes.
It is intended for people who want to **evaluate LLMs**, not necessarily contribute code.
For contributor onboarding see `docs/CONTRIBUTING.md`.

---

## What You'll Build

1. A project.
2. A small sample evaluation dataset (already provided in the repo).
3. A provider configuration (e.g. OpenAI, Anthropic).
4. An evaluation run that scores hallucination, faithfulness, answer relevancy, and more.

---

## Prerequisites

- A running RedOps deployment. See `docs/DEPLOYMENT.md`. For local evaluation use the
  development stack:

  ```bash
  docker compose -f docker/docker-compose.yml up -d
  ```

- A Browser (frontend at `http://localhost:5173`) or `curl` for the REST API.

---

## Step 1 — Create an account

Register via the UI (Sign up) or the API:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"change-me-strong"}'
```

The response returns a JWT access token. Use it as your bearer token for the steps below:

```bash
export TOKEN="<access-token>"
AUTH="Authorization: Bearer $TOKEN"
```

---

## Step 2 — Create a project

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"My First Eval"}'
```

Record the returned `project_id`.

---

## Step 3 — Load the sample dataset

A small, version-controlled sample dataset ships with the repo at
`scripts/sample_data/redops-sample-eval.jsonl`. It contains eight synthetic rows covering
correct, incorrect, irrelevant, hallucinated, grounded, and ungrounded answers.

Upload it as a dataset:

```bash
curl -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/datasets" \
  -H "$AUTH" \
  -F "name=Sample Eval" \
  -F "description=Eight canonical synthetic rows" \
  -F "file=@scripts/sample_data/redops-sample-eval.jsonl"
```

Record the returned `dataset_id`.

> All content is synthetic. No real user data is included.

---

## Step 4 — Configure a provider

Add an LLM provider (you must have an API key / key name for the provider you choose):

```bash
curl -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/providers" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"provider_name":"openai","config":{},"encrypted_api_key":"<your-key>"}'
```

The platform never returns API keys. See `docs/API_SPEC.md` → Provider Settings for the
supported provider names and fields.

---

## Step 5 — Create an experiment and run an evaluation

Create an experiment:

```bash
curl -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/experiments" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"Hallucination baseline"}'
```

Then start an evaluation run referencing the experiment, dataset, controller (which rows to
evaluate), and the metrics to score:

```bash
curl -X POST "http://localhost:8000/api/v1/experiments/$EXPERIMENT_ID/runs" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "name": "run-1",
    "dataset_id": "'"$DATASET_ID"'",
    "metrics": ["hallucination", "faithfulness", "answer_relevancy"]
  }'
```

The endpoint returns `202 Accepted` with a `workflow_id` referencing the Temporal workflow.
Poll the run resource (or subscribe via WebSocket — see `docs/API_SPEC.md`) until it completes.

---

## Step 6 — Review results

- View the run report and per-row scores in the dashboard.
- Open the **Reports** and **Dashboard** sections to see aggregated metrics.
- Re-run with different metrics or providers to compare.

---

## Going Further

- **CI/CD:** automate evaluation in pipelines with the provided `redops-gate` CLI and GitHub
  Action (see `redops-gate/README.md`). Add an `Idempotency-Key` header for safe retries.
- **Monitoring:** see `docs/MONITORING.md` for dashboards and metrics.
- **Red teaming:** create a red team campaign — see `docs/API_SPEC.md` → Red Team Campaigns.
- **Contributing:** see `docs/CONTRIBUTING.md`.
