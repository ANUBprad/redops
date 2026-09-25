# RedOps Eval — Monitoring

This document describes how to monitor a RedOps Eval deployment. Monitoring is powered by
**Prometheus** for scraping and **Grafana** for dashboards.

---

## Components

| File                     | Purpose                                          |
|--------------------------|--------------------------------------------------|
| `prometheus.yml`         | Prometheus scrape configuration                   |
| `grafana/dashboard.json` | Grafana dashboard (import into Grafana)           |

The API exposes metrics at `/metrics` (Prometheus text format). Deployment assets annotate pods
with `prometheus.io/scrape=true`, `prometheus.io/port=8000`, `prometheus.io/path=/metrics`.

---

## Scrape Targets (`prometheus.yml`)

| Job              | Target                          | Default scrape interval |
|------------------|---------------------------------|--------------------------|
| `redops-api`     | `redops-api:8000` (`/metrics`)  | 10s                      |
| `redis`          | `redis:6379`                    | 15s                      |
| `postgres`       | `postgres-exporter:9187`        | 15s                      |
| `temporal`       | `temporal:8233`                 | 15s                      |

Run Prometheus with:

```bash
prometheus --config.file=prometheus.yml
```

---

## Key Metrics

The Grafana dashboard (`grafana/dashboard.json`) visualizes the most important signals:

| Metric                                        | Meaning                                   |
|-----------------------------------------------|-------------------------------------------|
| `http_requests_total{method,status}`          | API request volume by method/status       |
| `http_request_duration_seconds_bucket`        | API latency (dashboard shows p95)         |
| `redops_evaluation_runs_active`               | Evaluation runs currently in progress     |
| `redops_evaluation_runs_completed_total`      | Cumulative completed runs                 |
| API attack/red-team violation counters        | Prompt-injection / jailbreak detections   |

Provider health is also available through the API's provider status endpoints, and per-route
rate limiting is exposed via `X-RateLimit-*` headers (see `docs/API_SPEC.md`).

---

## Import the Dashboard

1. Open Grafana → **Dashboards → Import**.
2. Upload `grafana/dashboard.json` (or paste its JSON).
3. Set the Prometheus data source.
4. Save.

---

## Alerting Guidance

Wire alert rules into Prometheus `alerting.alertmanagers` (currently empty by default). Suggested
alerts to configure:

| Condition                                          | Severity |
|----------------------------------------------------|----------|
| `up{job="redops-api"} == 0` (API down)             | critical |
| p95 latency > threshold for > 5m                   | warning  |
| `redops_evaluation_runs_active` stuck / no progress| warning  |
| High rate of red-team violations detected          | warning  |

Forwarding (Slack/PagerDuty) is configured via Alertmanager; see the Alertmanager docs for your
deployment.

---

## Release & Rollout

Use [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) before a public release. Confirm metrics are
flowing and the dashboard is populated as part of the rollout checklist.
