# RedOps Eval — Release Checklist

Go/No-Go checklist for every public release. Releasing is handled automatically by
semantic-release (see `.releaserc.json`), which bumps the version, updates the changelog, and
tags the release from Conventional Commit messages. This checklist covers the engineering and
deployment gates that must be green **before** a release ships.

---

## 1. Code Quality Gates

- [ ] **Backend lint:** `ruff check .` passes.
- [ ] **Backend format:** `ruff format --check .` passes.
- [ ] **Backend types:** `mypy --strict` passes.
- [ ] **Backend tests:** full `pytest` suite passes.
- [ ] **Frontend format:** `prettier --check .` passes.
- [ ] **Frontend lint:** `next lint` passes.
- [ ] **Frontend types:** `tsc --noEmit` passes.
- [ ] **redops-gate:** its test suite passes.

> Note: on Windows, `ruff format --check` and `prettier --check` may report style deltas due to
> `core.autocrlf` CRLF checkout. Verify with `git diff --numstat` — if it shows zero content
> changes, the committed files are fine and Linux CI will pass.

## 2. Security Gates

- [ ] `pip-audit` and `npm audit` jobs pass in CI.
- [ ] Trivy container scan (`.github/workflows/docker-build.yml`) reports no high/critical
      findings.
- [ ] Gitleaks secrets scan (`.github/workflows/secrets-scan.yml`) passes.
- [ ] No secrets, keys, or credentials introduced. `APP_SECRET_KEY` / `DB_PASSWORD` rotated.

## 3. Build & Images

- [ ] `.github/workflows/docker-build.yml` builds and pushes `redops/api` and
      `redops/frontend` for the release tag.
- [ ] Backend and frontend Dockerfiles are non-root and production-only dependency.

## 4. Database

- [ ] Any schema changes are covered by an Alembic migration.
- [ ] Migration is reversible (`alembic downgrade` supported).
- [ ] `alembic upgrade head` applied successfully in a staging environment.

## 5. Deploy & Verify

- [ ] Migrations applied before/at deploy.
- [ ] New API pods pass readiness: `GET /api/v1/ready` returns healthy.
- [ ] Liveness: `GET /api/v1/health` returns healthy.
- [ ] Smoke test an evaluation run end-to-end in staging.
- [ ] Rollback plan documented; Helm revision noted (`helm history`), previous image tag known.

## 6. Monitoring

- [ ] Prometheus is scraping the API (`up{job="redops-api"} == 1`).
- [ ] Grafana dashboard (`grafana/dashboard.json`) shows current metrics.
- [ ] Alerts configured and firing correctly.

## 7. Documentation & Communication

- [ ] `CHANGELOG.md` updated (semantic-release does this automatically).
- [ ] API docs reflect any new endpoints/fields (`docs/API_SPEC.md`).
- [ ] User-facing changes reflected in `docs/` (GETTING_STARTED, DEPLOYMENT, MONITORING).
- [ ] Breaking changes documented in the release notes.

---

## Not a Release (skip all of the above)

- Any work still on `develop` not merged to `main`.
- If a quality gate above is red — fixing it is the priority, not shipping.
