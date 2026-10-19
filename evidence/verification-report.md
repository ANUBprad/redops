# RedOps — Urgent Verification Sprint: Verification Report

- **Date:** 2026-10-19
- **Source commit under test:** `d437c731f75ddd9c12910ab8d96f920ca5be023f` (current `origin/main`)
- **Method:** a fresh, isolated `git clone` of that exact commit (never the user's
  working tree), real infrastructure (PostgreSQL, Redis, Temporal) in throwaway
  Docker containers on non-conflicting ports, real workflow execution with only
  provider/LLM *transport* stubbed where no live credential/credit exists.
- **Code fix produced by this sprint:** `479ddf278817d0c574c031bf0b2d022df5e9ddae`
  (`backend/app/infrastructure/database/models/base.py` +
  `backend/tests/infrastructure/database/test_datetime_columns_timezone_aware.py`)
- **Evidence directory:** `evidence/` (this directory; all artifacts sanitized).

## Verdict summary

| # | Verification task | Verdict | Basis |
|---|-------------------|---------|-------|
| 1 | Test totals (backend + frontend) | **PASS** | `3240 passed, 3 skipped` backend (exit 0); `31 passed / 6 files` frontend (exit 0). Raw logs in `test-results.txt`. |
| 2a | Temporal retry | **PASS** | Real `EvaluationRunWorkflow` on a real Temporal 1.24.2 server; controlled transient activity failure retried and the run completed. `temporal-retry-history.json`, `temporal-retry-summary.json`. |
| 2b | Temporal cancellation | **PASS** | Real `cancel` signal mid-run; in-flight item finished, remaining items never scheduled, run finalized as `cancelled`. `temporal-cancellation-history.json`, `temporal-cancellation-summary.json`. |
| 3 | Idempotent persistence | **PASS** | Real PostgreSQL; two identical writes converge to one row. `idempotency-report.json`, `idempotency-query.sql`, `idempotency-query-results.txt`. |
| 4 | Real provider calls (OpenAI, Anthropic, Groq) | **BLOCKED** | OpenAI reached the API but was rejected with HTTP 429 `insufficient_quota`; Anthropic and Groq have no credential. `provider-metadata.json`. |
| 5 | Metric sanity (safety, groundedness, cost) | **PASS** (algorithms) / **BLOCKED** (live judge model) | 24/24 checks on real `MetricEngine` + `JudgeEngine` + metric classes; judge *transport* scripted because no LLM credits exist. `metric-sanity-check.json`. |

**Overall: NOT fully qualified.** Tasks 1, 2, 3, and 5 (algorithmically) are
green. Task 4 and the live-judge half of task 5 are **BLOCKED on external
credentials/credits** and are not claimed as passing.

---

## 1. Test totals

Fresh-clone runs from the project roots.

| Suite | Command | Result |
|-------|---------|--------|
| Backend, pre-fix (`d437c73`) | `pytest -q` | `3238 passed, 3 skipped, 1 warning in 283.75s`, exit 0 |
| Backend, post-fix | `pytest -q` | `3240 passed, 3 skipped, 1 warning in 279.10s`, exit 0 |
| Frontend | `npx vitest run` | `6 passed (6)` files, `31 passed (31)`, exit 0 |

- The `+2` backend delta is exactly the new regression file (2 tests); no prior
  test changed state.
- The 3 backend skips are the opt-in live-provider smoke tests.
- `--reporter=basic` is unsupported by vitest v4.1.11 in this repo; the default
  reporter was used (noted so the counts are reproducible).

### The `3,200+` claim

There is **no** literal `3,200+` / `3200+` / `3.2k` claim on `d437c73`; it was
already removed earlier (`2f1a74f`). The remaining suite-size numbers
(`3,238`) live in `docs/RELEASE_CHECKLIST.md` (lines 14, 34) and
`docs/REDOPS_CREDIBILITY_GAP_AUDIT.md` (line 89), and both are explicitly
scoped to a *different* commit (`7f0adebd…`) and a *specific hosted CI run*
("145.80 seconds, 2 warnings"). They are precise, commit-qualified historical
records — not a claim about the current tree. They were therefore **left
unchanged**; editing them to `3,240` would misrepresent that historical run.

## 2. Temporal workflows

Real Temporal server `1.24.2` (`temporalio/auto-setup:1.25.0`), namespace
`default`, task queue `redops-verify-tq`. The real `EvaluationRunWorkflow` and
its real production retry policies were used; only the item *activity body* was
stubbed (deterministic token-count result), so no provider call was mocked.

### 2a. Retry — PASS

- Workflow `redops-verify-retry-20261019-090819`, server status `COMPLETED`,
  result `status="completed"`, `items_completed=1`.
- Worker-side attempt counter for item 0 = **2** (first call raised a controlled
  transient error, second succeeded).
- Production retry policy exercised: `maximum_attempts=3`,
  `initial_interval=2s`, `backoff=2.0`.
- History shows a single `ActivityTaskScheduled` for that activity followed by an
  `ActivityTaskStarted` with `attempt=2` and
  `last_failure.message="controlled transient failure on attempt 1"`, then
  `ActivityTaskCompleted` (41 events total). A minimal isolated probe
  (`harness/probe_retry_history.py`, output `temporal-retry-shape-probe.json`)
  reproduced this identical history shape, confirming it is genuine Temporal
  1.24.2 behaviour and not an artifact of the harness.

### 2b. Cancellation — PASS

- Workflow `redops-verify-cancel-20261019-090754`, server status `COMPLETED`
  (the cancel is handled gracefully and the workflow finalizes), result
  `status="cancelled"`, `items_completed=1`, `items_total=3`,
  `item_indices_executed=[0]`.
- Timeline: the in-flight item-0 activity started, the `cancel` signal was
  recorded **~124 ms** into the 3 s activity, item 0 was allowed to finish, and
  items 1 and 2 were **never scheduled**. A single `cancel_run_activity` ran
  (39 events total).

## 3. Idempotent persistence (+ defect found and fixed)

Real PostgreSQL (throwaway container), Alembic head `024`. Identity:
`metric_results` unique key `uq_metric_results_run_item_metric`
(`run_id, item_id, metric_name`); durable `(run_id, item_id)` composite PK on
`item_executions`.

- **Pre-fix:** the very first `persist_metric_results_activity` call **failed**
  on PostgreSQL — `asyncpg.exceptions.DataError: invalid input for query
  argument $11 … (can't subtract offset-naive and offset-aware datetimes)`
  against `$11::TIMESTAMP WITHOUT TIME ZONE`. (The full SQLite suite passed
  because SQLite ignores the timezone distinction.)
- **Post-fix:** two identical submissions converge to exactly one row —
  `metric_row_count=1`, `metric_distinct_ids=1`, `first_id=last_id=1`, and
  `created_at = 2026-10-19T09:22:49.056666+00:00` stored as `timestamptz`. Two
  durable `_write_durable_execution` calls converge to `durable_row_count=1`.

### Root cause and fix

Every timestamp column produced by the migrations is `TIMESTAMP WITH TIME ZONE`
(verified against the live DB: **126 / 126** timestamp columns are
`timestamp with time zone`; zero naive), and the application only ever binds
aware UTC datetimes. Several ORM models already spelled this explicitly
(`DateTime(timezone=True)`), but the bare `Mapped[datetime]` columns inherited
SQLAlchemy's **naive** default. The Core `postgres_insert(...)` executemany in
`metric_result_repository.save_many` therefore compiled a
`::TIMESTAMP WITHOUT TIME ZONE` bind cast, which asyncpg rejects for aware
values.

Fix (one place, root cause): `Base.type_annotation_map` now maps bare
`datetime` to `DateTime(timezone=True)`, matching the schema. Explicit
per-model declarations are unaffected. This is the shared-cause fix rather than
patching a single call site.

Blast radius was measured, not assumed: `metric_result_repository` is the only
repository issuing a Core `insert()` executemany (the concrete breakage); the
ORM-flush durable `item_executions` path did **not** reproduce the failure
pre-fix, but is corrected all the same because its declared type disagreed with
the schema. Detail: `postgres-naive-datetime-defect.txt`.

Regression test `backend/tests/infrastructure/database/test_datetime_columns_timezone_aware.py`:
**fails pre-fix (2 failed), passes post-fix (2 passed)**.

## 4. Real provider calls — BLOCKED

One real minimal chat request per adapter (`provider-metadata.json`):

| Provider | Model | Credential | Outcome |
|----------|-------|-----------|---------|
| OpenAI | `gpt-4o-mini` | present | **BLOCKED** — real call reached the API, HTTP 429 `insufficient_quota` / `credit_balance_exhausted` ("no credits remaining") |
| Anthropic | `claude-sonnet-4-20250514` | absent | **BLOCKED** — no credential |
| Groq | `llama-3.3-70b-versatile` | absent | **BLOCKED** — no credential |

Opt-in smoke run: `1 failed, 2 skipped` (`tests/providers/test_live_provider_smoke.py`),
consistent with the above. No real call is reported as passing, and no real call
was replaced with a mock.

## 5. Metric sanity — PASS (algorithms) / BLOCKED (live judge model)

Real `MetricEngine`, real `JudgeEngine`, and the real `safety`,
`groundedness`, and `cost` metric implementations were exercised against a
small deterministic fixture. The only substituted component is the judge's
**transport** (a deterministic scripted chat provider), because no LLM credits
are available; **no live judge model was called.** `metric-sanity-check.json`
records 24 checks, all passing:

- Safety verdict tracks the judge output (1.0 → 1.0, 0.1 → 0.1).
- Groundedness tracks the judge output (1.0 → 1.0, 0.0 → 0.0), and the judge
  prompt is actually built from the fixture prompt/response/context.
- Judge provenance is recorded (`judge_model`, `rubric_version=1.0.0`,
  `judge_prompt_version=1.0.0`, provider, token counts); `cost_estimated=true`
  for `gpt-4o-mini`, `false` for an unknown `claude` model
  (provenance follows the configured model).
- Groundedness without context is an explicit error with **0** judge calls
  (no fabricated score).
- Cost matches the documented `1 - log1p(cost)/log1p(0.10)` formula across
  0.0 / 0.001 / 0.01 / 0.05 / 0.10 / 1.0; missing `cost_usd` is an explicit
  error.

Because the judge was not called live, the *algorithmic* behaviour is verified
but the end-to-end metric path against a real frontier judge remains
**BLOCKED**.

---

## Blockers (external, unverifiable in this environment)

1. **No LLM credits/keys** — OpenAI returns 429 `insufficient_quota`; Anthropic
   and Groq keys are absent. Blocks task 4 entirely and the live-judge half of
   task 5.
2. **`temporal` admin CLI hang** — the `temporalio/admin-tools` image hung on
   `temporal operator cluster health`; worked around by using the Temporal
   Python SDK for all server interaction (no functional loss).

## Remaining unverified

- Real OpenAI / Anthropic / Groq provider responses with valid credentials.
- A live frontier judge model driving safety/groundedness end-to-end.
- Staging deployment, migration-in-staging, rollback drill, Prometheus/Grafana
  alerting, and independent license-cleared ground-truth accuracy — all
  out of scope for this sprint and unchanged.
- The reported defect was found and fixed for the metric-result write path;
  repository-wide behavioural parity under PostgreSQL (beyond the paths
  exercised here) was not exhaustively re-run.

## Commits

- Source verified: `d437c731f75ddd9c12910ab8d96f920ca5be023f`
- Fix + regression test: `479ddf278817d0c574c031bf0b2d022df5e9ddae`
