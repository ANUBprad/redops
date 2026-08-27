# RedOps Eval — Deployment Guide

This document describes how to deploy RedOps Eval to production. It covers the containerized
stack, Kubernetes manifests, Helm chart, and the monitoring stack (Prometheus + Grafana).

> **Scope:** Production deployment. For local development see `README.md` and
> `docs/GETTING_STARTED.md`.

---

## Deployment Options

| Option                 | Location                         | Use case                                  |
|------------------------|----------------------------------|--------------------------------------------|
| Docker Compose (dev)   | `docker/docker-compose.yml`      | Local development                         |
| Docker Compose (prod)  | `docker/docker-compose.prod.yml` | Single-host production / small previews   |
| Kubernetes base        | `kubernetes/base/`               | Manual `kubectl apply` on any cluster      |
| Helm chart             | `helm/redops/`                   | Production installs, config via `values`   |
| Monitoring             | `prometheus.yml`, `grafana/`     | Metrics + dashboards                       |

The API and frontend are also shipped as hardened OCI images (non-root, production-only
dependencies) via `.github/workflows/docker-build.yml`:

- `redops/api` — FastAPI backend
- `redops/frontend` — Next.js 15 static/standalone build

---

## Architecture Overview

A production deployment requires the following services:

1. **API** — FastAPI application (the only service exposed externally).
2. **Frontend** — Next.js standalone server, served over the API or via CDN.
3. **PostgreSQL 16** — primary data store.
4. **Redis 7** — event bus (Redis Streams), rate limiting, cache.
5. **Temporal** — durable workflow orchestration for evaluation runs and red-team campaigns.
   (Temporal UI/admin are optional, internal-only.)

All services attach to a private network. Only the API and Frontend receive ingress.

---

## Configuration

Configuration is delivered through environment variables. The production-required variables
are:

| Variable          | Description                                        | Example                          |
|-------------------|----------------------------------------------------|----------------------------------|
| `APP_ENV`         | Runtime environment                                | `production`                     |
| `APP_DEBUG`       | Disable debug mode                                 | `false`                          |
| `APP_LOG_LEVEL`   | Log verbosity                                       | `INFO`                           |
| `APP_SECRET_KEY`  | Signing secret (JWT). **Never commit.**             | `<random>`                       |
| `DB_HOST`         | PostgreSQL host                                     | `postgres.redops.svc...`         |
| `DB_PORT`         | PostgreSQL port                                     | `5432`                           |
| `DB_USER`         | DB user                                             | `redops`                         |
| `DB_PASSWORD`     | DB password. **Never commit.**                      | `<random>`                       |
| `DB_NAME`         | Database name                                       | `redops`                         |
| `REDIS_HOST`      | Redis host                                          | `redis`                          |
| `REDIS_PORT`      | Redis port                                          | `6379`                           |
| `TEMPORAL_HOST`   | Temporal server host                                | `temporal`                       |
| `TEMPORAL_PORT`   | Temporal gRPC port                                  | `7233`                           |
| `SERVER_CORS_ORIGINS` | Allowed CORS origins (comma-separated)          | `https://app.redops.example.com` |

> **Security:** Rotate `APP_SECRET_KEY` and `DB_PASSWORD`. In Kubernetes use a Secret (see
> `helm/redops/templates/secret.yaml`). Never store secrets in image layers or source control.

A complete local reference is available in `.env.example`.

---

## Option A: Docker Compose (single host)

The provided `docker/docker-compose.yml` targets **development** (it mounts source volumes and
runs an unoptimized frontend dev server). For a single-host production deployment, provide your
own compose file that:

- Uses the built `redops/api` and `redops/frontend` images.
- Does **not** mount source directories.
- Sets `APP_ENV=production`, `APP_DEBUG=false`.
- Ships secrets via an environment file or Docker secrets.

A production-style compose file is provided at `docker/docker-compose.prod.yml`. It uses the
built `redops/api` and `redops/frontend` images (no source mounts, hardened non-root images)
and reads secrets from the environment:

```bash
export DB_PASSWORD="$(openssl rand -hex 32)"
export APP_SECRET_KEY="$(openssl rand -hex 32)"
docker compose -f docker/docker-compose.prod.yml up -d
```

This is suitable for a single host / small preview. For anything larger or HA, prefer
Kubernetes (Option B/C).

---

## Option B: Kubernetes Manifests

Base manifests live in `kubernetes/base/`:

```
kubernetes/base/
├── namespace.yaml          # redops namespace
├── configmap.yaml          # non-secret env config
├── secret.yaml             # DB password, app secret (edit before apply)
├── api-deployment.yaml     # API Deployment (replicas, probes, resources)
├── api-service.yaml        # API ClusterIP service
├── api-ingress.yaml        # Ingress (TLS via cert-manager)
└── test-connection.yaml    # optional connectivity smoke test
```

Apply in order:

```bash
kubectl create namespace redops
kubectl apply -f kubernetes/base/
```

Dependencies (PostgreSQL, Redis, Temporal) are expected to be provisioned in the same cluster
(`postgres.redops.svc.cluster.local`, `redis.redops.svc.cluster.local`) or reachable via
`configmap.yaml` overrides.

---

## Option C: Helm Chart (production Kubernetes)

The Helm chart lives in `helm/redops/`. It deploys the **API** as a Deployment with
autoscaling, probes, ingress, a service account, and a ConfigMap that wires the API's
non-secret environment (PostgreSQL, Redis, and Temporal connection settings).

> **Prerequisite:** The chart expects **external** PostgreSQL, Redis, and Temporal servers
> reachable from the cluster (configured via `config` / `secrets` values). It does not bundle
> those dependencies, and the worker runs in-process with the API (there is no separate
> worker Deployment). For an all-in-one stack, use Option A or the Kustomize base.

### Install

```bash
helm upgrade --install redops helm/redops \
  --namespace redops \
  --create-namespace \
  --set image.tag=<version> \
  --set secrets.dbPassword=<password> \
  --set secrets.appSecretKey=<secret> \
  --set ingress.hosts[0].host=api.redops.example.com \
  --set ingress.tls[0].hosts[0]=api.redops.example.com
```

### Key values (`helm/redops/values.yaml`)

| Value         | Default            | Notes                                |
|---------------|--------------------|--------------------------------------|
| `replicaCount`| `2`                | Starting replicas                    |
| `autoscaling` | `enabled: true`    | HPA, min 2 / max 10                  |
| `ingress`     | `enabled: true`    | NGINX + cert-manager TLS            |
| `service.port`| `80` -> `8000`     | ClusterIP to container               |
| `config.*`    | see values.yaml    | Non-secret env (DB/REDIS/TEMPORAL) via ConfigMap |
| `secrets.*`   | `CHANGE_ME`        | **Must set before production**       |
| `resources`   | 250m / 1Gi         | Container requests/limits            |

### Upgrade / rollback

```bash
helm upgrade --install redops helm/redops --namespace redops
helm rollback redops <revision> --namespace redops
helm list -n redops
```

---

## Frontend Deployment

The frontend is a Next.js 15 app built with `output: "standalone"`. The production image
(`frontend/Dockerfile`) contains a minimal standalone server.

- **Same origin:** Serve the frontend from the same domain as the API and set
  `VITE_API_URL`/`NEXT_PUBLIC_API_URL` to `/api/v1`.
- **Separate origin:** Set the public API base URL at build time and configure
  `SERVER_CORS_ORIGINS` on the API to allow the frontend origin.

---

## Database Migrations

Run Alembic migrations against the target database before/at deploy time:

```bash
cd backend
alembic upgrade head
```

In CI, run migrations as a job, then start the API. Do not run the API against a database whose
schema is ahead, to avoid `Idempotency-Key`/uniqueness errors at runtime.

---

## Monitoring

- **Prometheus** scrape config: `prometheus.yml` (API `/metrics`, Redis, Postgres exporter,
  Temporal).
- **Grafana** dashboard: `grafana/dashboard.json`.

See `docs/MONITORING.md` for scrape targets, key metrics, and alerting guidance.

---

## Release & Rollout Checklist

Follow `docs/RELEASE_CHECKLIST.md` before every public release. In short:

1. Version bump + changelog (semantic-release does this automatically — see `.releaserc.json`).
2. Backend: `ruff`, `mypy`, full `pytest` suite green.
3. Frontend: `prettier`, `eslint`, `tsc --noEmit` green.
4. `docker-build.yml` builds and pushes images; Trivy scan has no high/critical findings.
5. Migrations applied; smoke-test `/api/v1/health` and `/api/v1/ready` on the new API.
6. Rollback plan documented; Helm revision noted.

---

## Troubleshooting

| Symptom                                  | Likely cause & fix                                  |
|------------------------------------------|------------------------------------------------------|
| API `/api/v1/health` fails               | Dependency down — check Postgres/Redis/Temporal reachability. |
| `/api/v1/ready` returns 503              | Readiness probe target unavailable; check DB readiness.       |
| `Idempotency-Key` collisions             | Multiple API pods sharing a pool — key is scoped by team; ensure the key path is consistent and retries use the same body. |
| 429s despite low traffic                 | Rate limit is per-route/per-team; raise via `route_limits` or `X-RateLimit-*` headers. |
| Temporal workflows not progressing       | Temporal server unreachable from API pod (`TEMPORAL_HOST`/`TEMPORAL_PORT`). |
