# RedOps Eval — Release Checklist

Go/No-Go checklist for every public release. Releasing is handled automatically by
semantic-release (see `.releaserc.json`), which bumps the version, updates the changelog, and
tags the release from Conventional Commit messages. This checklist covers the engineering and
deployment gates that must be green **before** a release ships.

---

## Current Release Assessment — 2026-10-16

**Decision: NO-GO for v0.1.0 until the remaining evidence is attached.**

Source commit `12a4aae7b329b71fabe714b48e28edf3c80f55e3` passed hosted backend/frontend CI, Docker builds, Trivy HIGH/CRITICAL vulnerability gate, and Gitleaks. Backend: 3,238 passed, 1 third-party `passlib`/`crypt` deprecation warning; frontend: 31 passed. Backend/frontend lint, type, security, build, and test jobs passed. The coverage artifact uploaded successfully. Live-provider and staging evidence is still missing, so the release decision remains NO-GO.

The following are **not verified by source review or unit tests alone** and must remain unchecked until evidence is recorded:

- Real OpenAI, Anthropic, and Groq provider calls using valid credentials.
- A browser-started red-team run that executes the selected persisted definition, persists round evidence, and renders that evidence in the UI.
- Live Temporal cancellation/retry and duplicate-persistence checks.
- Staging deployment and migration verification.
- Rollback drill with the prior image/tag recorded.
- Prometheus scraping, Grafana dashboard review, and alert firing.
- Successful Trivy/Gitleaks scans on the release candidate.
- Independent, license-cleared ground-truth validation. The checked-in synthetic fixture is not ground truth and must not be used to claim metric accuracy.

Attach workflow links, sanitized provider-run evidence, staging URLs/logs, and the rollback/monitoring evidence to the release PR before changing this decision.

## 1. Code Quality Gates

- [x] **Backend lint:** `ruff check .` passes in CI.
- [x] **Backend format:** `ruff format --check .` passes in CI.
- [x] **Backend types:** `mypy app/` passes in CI with `strict = true` in `pyproject.toml`.
- [x] **Backend tests:** full pytest suite passes (3,238 passed; one third-party deprecation warning).
- [x] **Frontend format:** `prettier --check .` passes in CI.
- [x] **Frontend lint:** the configured ESLint job passes in CI.
- [x] **Frontend types:** `tsc --noEmit` passes in CI.
- [ ] **redops-gate:** its test suite passes.

> Note: on Windows, `ruff format --check` and `prettier --check` may report style deltas due to
> `core.autocrlf` CRLF checkout. Verify with `git diff --numstat` — if it shows zero content
> changes, the committed files are fine and Linux CI will pass.

## 2. Security Gates

- [x] `pip-audit` and `npm audit` jobs pass in CI.
- [x] Trivy container scan (`.github/workflows/docker-build.yml`) passed with the HIGH/CRITICAL gate on the audited source commit.
- [x] Gitleaks secrets scan (`.github/workflows/secrets-scan.yml`) passes on the audited source commit.
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
- [x] User-facing audit/validation/release status changes reflected in `README.md` and `docs/`.
- [ ] Breaking changes documented in the release notes.

---

## Not a Release (skip all of the above)

- Any work still on `develop` not merged to `main`.
- If a quality gate above is red — fixing it is the priority, not shipping.
