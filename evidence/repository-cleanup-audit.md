# Repository Cleanup Audit

Audit date: 2026-10-20
Method: evidence-based. Nothing was deleted or ignored on the basis of filename,
age, or size alone. Every candidate below is resolved by a reference / import /
CI / doc / test search whose result is recorded inline.

Commands used (read-only):

```bash
git ls-files                       # 1156 tracked files, 6.18 MB total
git ls-files | xargs stat          # per-file size
git grep <path/symbol>             # reference search
```

## 1. Inventory summary

| Area | Tracked files |
|---|---|
| `backend/` | 910 |
| `frontend/` | 109 |
| `evidence/` | 33 |
| `docs/` | 28 |
| `tests/` (repo root) | 17 |
| `.github/` | 10 |
| `helm/`, `kubernetes/`, `redops-gate/`, `plugins/`, `docker/`, `scripts/`, `grafana/` | 40 |
| root files (`README`, `CHANGELOG`, `LICENSE`, `SECURITY`, config) | 10 |

Largest tracked files are all legitimate lockfiles / test suites / evidence JSON
(`backend/uv.lock` 380 KB, `frontend/package-lock.json` 326 KB, largest test
module 47 KB). No tracked file is a build artifact.

## 2. Categories checked and outcome

### 2.1 Build artifacts and caches — PASS (no action)

`git ls-files` was filtered for `.pyc`, `__pycache__`, `node_modules`,
`.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.coverage`, `htmlcov`, `*.log`,
`*.zip`, `*.tar`, `*.whl`, `*.egg-info`, `.DS_Store`, `*.db`, `*.sqlite`.
Result: **zero tracked matches**. `.gitignore` already covers all of these
patterns plus `frontend/.next/`, `coverage.xml`, `.venv/`, `.env`.

### 2.2 Untracked files at repo root

| Path | Disposition | Evidence |
|---|---|---|
| `AGENTS.md` | **keep untracked** | Project agent-rules document; user-owned. `git status` shows it as untracked and it is referenced by `AUTONOMOUS_MASTER_PROGRESS.md` ("Manifesto/AGENTS.md applies"). Not deleted, not added to `.gitignore` (it is a rules file a maintainer may want to commit). |
| `AUTONOMOUS_MASTER_PROGRESS.md` | **keep untracked** | Active user backlog file (DONE/READY/DISCOVERED unit tracker). User-owned working state. |
| `graphify-out/` | **keep untracked** | Generated output of the user's `graphify` tooling. No tracked file references it. Left alone; not deleted because it is tooling output the user may be mid-way through. |
| `login.json` | **keep untracked, content inspected** | Contains a demo/stub credential pair (`test@example.com` / `password123`), not a real secret. Left untouched. See 2.5 for the `.gitignore` recommendation. |

### 2.3 Root `tests/` directory vs `backend/tests/` — REDUNDANT, deletion proposed

Finding: the repo root contains a second, older copy of nine test modules that
also exist under `backend/tests/`. Evidence of redundancy:

1. **Same test functions.** AST comparison of module-level `test_*` functions
   shows identical function-name sets in all nine pairs, with zero root-only
   tests:

   | Module | root-only tests | backend-only tests |
   |---|---|---|
   | `test_success_criteria.py` | 0 | 0 |
   | `apikeys/test_domain.py` | 0 | 0 |
   | `audit/test_entities.py` | 0 | 0 |
   | `identity/test_entities.py` | 0 | 0 |
   | `notification/test_entities.py` | 0 | 0 |
   | `project/test_entities.py` | 0 | 0 |
   | `rbac/test_permissions.py` | 0 | 0 |
   | `scheduling/test_domain.py` | 0 | 0 |
   | `tenant/test_entities.py` | 0 | 0 |

   Two (`notification/test_entities.py`, `apikeys/test_domain.py`) are
   byte-identical; the rest differ only in small edits made after the split.

2. **No references.** A full-text scan of every tracked file outside `tests/`
   for each of the nine paths returned zero matches (`tests/identity/` appears
   in `README.md` only as the non-existent path `pytest tests/identity/`, which
   is a stale README example — see 2.4).

3. **Not run in CI.** `.github/workflows/ci-backend.yml` runs with
   `working-directory: backend` and executes `pytest` there; the workflow's
   `paths` filter is `backend/**`, so changes to root `tests/` do not even
   trigger it. `ci-frontend.yml` covers only `frontend/**`.

4. **Not part of the documented suite.** The documented commands in
   `README.md` (§ Development) are run from `backend/`, and the current
   verified suite count (3243 passed / 3 skipped) comes from `backend/`.
   Root-level collection only happens if pytest is invoked from the repo root,
   which the README never instructs and which is broken anyway
   (`asyncio_mode = "auto"` lives in `backend/pyproject.toml`).

5. **Provenance.** Introduced in `83d74cb` ("feat: complete enterprise
   platform, production readiness, and agent runtime") before the suite moved
   under `backend/`; superseded by the `backend/tests/` copies.

**Proposed action:** delete the old root copies (`tests/` minus `__init__.py`
guards). The identical, maintained copies remain in `backend/tests/` and remain
in the CI suite, so no test coverage is lost.

`git rm` is deferred to the maintainer (see §3): deleting 17 tracked files in an
otherwise provider-focused change is a review burden, and the repository rules
forbids multi-purpose commits.

### 2.4 Documentation accuracy

| Finding | Evidence | Action |
|---|---|---|
| `README.md` lists `pytest tests/identity/` as an "Auth tests" example. No such path exists in either `backend/tests/` or the root `tests/`; the nearest real coverage is `backend/tests/rbac/` + `backend/tests/tenant/`. | `Test-Path backend/tests/identity` → false; `git ls-files` shows no `identity/` test dir under `backend/`. | **Fixed in this sprint** (README correction). |
| `README.md` claimed "Without keys, the provider registry registers only mock/fallback providers". No mock/fallback provider is registered anywhere: `container._register_providers` registers only keyed providers, and a scan for `MockProvider` / `FallbackProvider` classes found no provider implementation. | `grep -r "MockProvider\|FallbackProvider" backend/app` → only `ProviderRuntimeError` strings. | **Fixed in this sprint** (README correction). |
| `docs/index.md` does not link `docs/evaluation/METRIC_VALIDATION.md`, and no other tracked file references it (only orphan doc in the tree). | Cross-reference scan of all 40 tracked `.md` files. | **Kept.** The document is coherent, describes the metric-validation pipeline that `scripts/validate_metrics.py` implements, and has a companion `docs/METRICS_VALIDATION_REPORT.md`. Adding a single index row is an editorial change outside this sprint's scope; recorded here so it is not re-flagged. |

No duplicate doc content was found: a SHA-256 comparison of all tracked `.md`
and `.jsonl` files returned zero content duplicates.

### 2.5 Text encoding

A scan of every tracked UTF-8 text file for CP1252 mojibake sequences
(`â€”`, `Ã©`, `â€œ`, U+FFFD, …) found exactly one damaged file:

- `backend/tests/redteam/temporal/test_metrics_persistence_retryability.py` —
  three comments/docstring lines contained `â€”` where an em dash (`—`) was
  intended (a UTF-8 → CP1252 → UTF-8 round-trip artifact).

**Fixed in this sprint**: the three occurrences were replaced with `—`.
Re-scan result: `total files with mojibake markers: 0`. No other tracked file
is non-UTF-8 (scan of all 1156 files).

### 2.6 `.gitignore` gaps

Two gaps were found and **fixed in this sprint**:

1. **Generated harness output was unignored.** `evidence/harness/verify_metric_sanity.py`
   writes `evidence/harness/metric-evidence/metric-sanity-check.json` and
   `evidence/harness/verify_providers.py` writes
   `evidence/harness/provider-evidence/provider-metadata.json`. Neither
   directory was ignored, so every harness run dirtied the working tree.
   The committed copies at `evidence/metric-sanity-check.json` and
   `evidence/provider-metadata.json` are the durable evidence; the harness-local
   directories are regenerated output. Adding both to `.gitignore` keeps the
   tracked evidence records stable and re-runnable.
   Evidence: both paths are created by `Path(__file__).resolve().parent / …`
   in the two harness scripts, and the fresh files differ from the committed
   ones (`sha256` prefix `2f394083…` vs `f6ebf54f…`; `22ffacf9…` vs
   `f40eb3d2…`).

2. **`login.json` (repo root) is untracked and *not* ignored.** It currently
   contains a placeholder credential pair (`test@example.com` / `password123`),
   not a real secret, so no rotation is needed — but the filename is a
   credential-shaped artifact that `git add .` would happily commit.

**Applied:** `.gitignore` now ignores `evidence/harness/metric-evidence/` and
`evidence/harness/provider-evidence/`.

**Recommended, not applied:** add `login.json` to `.gitignore`. Not applied
because the file is the maintainer's local tool state and may be deleted or
replaced by a redacted `login.example.json` instead; the `.env` / `.env.*`
credential path that matters for production is already ignored (with
`!.env.example`).

### 2.7 Retained without change (deliberately)

| Area | Why retained |
|---|---|
| `evidence/**` (33 files) | Verification artifacts for prior sprints (Temporal retry/cancel histories, PostgreSQL idempotency queries, metric-sanity JSON, fresh resume-sprint re-runs). Repository rules require preserving existing evidence. The `evidence/resume-sprint/*-fresh*` files intentionally duplicate shapes from `evidence/*` with fresh timestamps — that is the evidence, not redundancy. |
| `helm/`, `kubernetes/`, `docker/`, `grafana/`, `prometheus.yml`, `.releaserc.json`, `SECURITY.md` | All referenced by CI, `docs/DEPLOYMENT.md`, `docs/RELEASE_CHECKLIST.md`, `docs/MONITORING.md`, or `backend/tests/test_readiness.py`. |
| `scripts/validation_data/**`, `scripts/sample_data/**`, `scripts/validate_metrics.py`, `scripts/bootstrap.sh` | Referenced by `.github/workflows/ci-backend.yml`, `backend/tests/scripts/test_validate_metrics.py`, `backend/tests/evaluation/validation/test_loader.py`, `docs/GETTING_STARTED.md`, and `docs/index.md`. |
| `redops-gate/`, `plugins/` | Referenced by `docs/GETTING_STARTED.md`, `docs/ROADMAP.md`, `docs/RELEASE_CHECKLIST.md`, and `backend/app/evaluation/metrics/registry.py`. |
| `docs/METRICS_VALIDATION_REPORT.md`, `docs/REDOPS_CREDIBILITY_GAP_AUDIT.md` | Referenced by `README.md`, `evidence/verification-report.md`, and `scripts/validation_data/README.md`. |
| `CHANGELOG.md`, `LICENSE`, `.editorconfig`, `.pre-commit-config.yaml` | Standard root metadata, referenced by `.pre-commit-config.yaml` consumers and docs. |

## 3. Deletion proposal (maintainer decision)

| # | Path | Files | Confidence | Rationale |
|---|---|---|---|---|
| 1 | `tests/` (root) | 17 | **High** — superseded duplicates, unreferenced, outside CI and the documented suite | See 2.3. Recommend `git rm -r tests/` as its own commit so it can be reviewed and reverted independently of the provider work. |

Nothing else in the audit meets the bar for deletion: every other candidate is
referenced by CI, tests, or documentation.

## 4. Applied in this sprint

| Change | Evidence |
|---|---|
| Fixed 3 mojibake em dashes in `backend/tests/redteam/temporal/test_metrics_persistence_retryability.py` | mojibake re-scan → 0 files |
| Corrected stale `pytest tests/identity/` README example | README diff |
| Corrected false "registers only mock/fallback providers" README claim | README diff, `container._register_providers` source |
| Ignored generated harness output dirs (`evidence/harness/metric-evidence/`, `evidence/harness/provider-evidence/`) | `git check-ignore -v` → `.gitignore:53/54` |

## 5. Not actioned

- `login.json` → `.gitignore` (recommended, not applied — see 2.6).
- Root `tests/` deletion (proposed, not applied — see §3).
- `docs/evaluation/METRIC_VALIDATION.md` index link (editorial, see 2.4).
