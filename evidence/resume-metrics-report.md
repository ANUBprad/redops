# RedOps — Resume Metrics Verification Sprint

- **Date:** 2026-10-19
- **Commit under test (backend):** `48689727656dea58c442fa42b1bfb02235fd61f8` (current `origin/main`)
- **Method:** genuine fresh `git clone` of that exact commit into an isolated directory
  (never the user's working tree), global CPython 3.12.7, clone's `app` package verified to
  shadow the editable install (`app.__file__` resolves inside the clone) so no local-tree
  code leaked into the results. Raw logs: `evidence/resume-sprint/`.
- **`opencode.md`:** does not exist in this repository; the sprint followed the task's
  mandatory rules and `AGENTS.md` instead.

## A. Test results

### Backend

| Item | Value |
|---|---|
| Commit | `48689727656dea58c442fa42b1bfb02235fd61f8` |
| Python | 3.12.7 (global interpreter; deps per `backend/pyproject.toml` `[dev]`: pytest, pytest-asyncio, aiosqlite, …) |
| Command (from `backend/`) | `python -m pytest -q` |
| **Passed** | **3243** |
| Failed | 0 |
| Errors | 0 |
| Skipped | 3 |
| Warnings | 2 (starlette/httpx deprecation, third-party) |
| Exit code | 0 |
| Duration | 372.78 s |
| Log | `evidence/resume-sprint/backend-test-output.txt` |

The 3 skips are the opt-in live-provider smoke tests
(`tests/providers/test_live_provider_smoke.py::test_live_{openai,anthropic,groq}_chat`),
skipped by design without live credentials. Skips are **not** counted as passing.

### The reported "17 errors"

Not reproducible from any fresh clone:

| Invocation | Result | Classification |
|---|---|---|
| Fresh clone `4868972`, from `backend/` (documented) | `3243 passed, 3 skipped`, exit 0 | clean |
| Fresh clone of pre-sprint local main `43714a5`, from `backend/` | `3231 passed, 9 warnings`, exit 0, **0 errors** | clean |
| Fresh clone `4868972`, run from **repo root** (wrong cwd) | `329 failed, 2881 passed, 108 errors` — all errors `async def functions are not natively supported` | **environmental / invocation error**: `backend/pyproject.toml`'s `[tool.pytest.ini_options] asyncio_mode = "auto"` is not loaded when pytest runs from the repo root, so every async test errors or fails. Not a code defect. |

The 17-error report cannot be attributed to current or pre-sprint code; the only
error-producing invocation found is the wrong-cwd one above (which produces 108, not 17).
No repository defect was found or fixed for it.

### Frontend

| Item | Value |
|---|---|
| Commit | `4868972…` code + the lockfile fix committed in this sprint (tree identical to that fix commit) |
| Setup | `npm ci` (497 packages) |
| Command | `npx vitest run` |
| **Test files passed** | **6 passed (6)** |
| **Tests passed** | **31 passed (31)** |
| Failed / skipped | 0 / 0 |
| Exit code | 0 |
| Duration | 13.92 s |
| Log | `evidence/resume-sprint/frontend-test-output.txt` |

**Genuine defect found and fixed:** on a fresh clone of `4868972`, `npm ci` failed with
`EUSAGE` — `package-lock.json` was out of sync with `package.json`
(missing `@tailwindcss/postcss@4.3.3`; `@typescript-eslint/*@8.66.0` vs required `8.71.2`;
`@vitest/coverage-v8@3.2.7` vs required `^4.1.12`). Root cause: the conflict resolution in
`1ef0ffe` accidentally committed a stale local lockfile over the valid one from `ad3e53c`
(ad3e53c's lockfile verified in sync via `npm ci --dry-run`, exit 0). Fix: restored the
`ad3e53c` lockfile; `npm ci` then succeeded (exit 0) and the suite passed. The report's
frontend numbers were produced on exactly the fixed tree.

### Reproducibility

```bash
git clone https://github.com/ANUBprad/redops && cd redops
cd backend && pip install -e ".[dev]" && python -m pytest -q   # 3243 passed, 3 skipped
cd ../frontend && npm ci && npx vitest run                     # 6 files, 31 passed
```

## B. Evaluation results (safety, groundedness, cost)

Fresh run of `evidence/harness/verify_metric_sanity.py` against the current `main` code
(clone pinned via `PYTHONPATH`), real `MetricEngine` + real `JudgeEngine` + real metric
classes (`SafetyMetric`, `GroundednessMetric`, `CostMetric`). Run/eval ID:
`metric-sanity-run`. **24/24 checks PASS** (`evidence/resume-sprint/metric-sanity-check-fresh.json`).

| Metric | Value | Range | Inputs (redacted) | Judge/evaluator | Raw sources | Calculation | Evidence status |
|---|---|---|---|---|---|---|---|
| Safety | **1.0** (benign fixture), **0.1** (harmful fixture) | 0–1 | prompt "How do I bake a chocolate cake?" / response "Preheat the oven to 180C…"; harmful twin | llm-judge, model `gpt-4o-mini`, rubric v1.0.0, judge-prompt v1.0.0 | injected judge verdicts {score:1.0} and {score:0.1}; tokens 142 in / 23 out | `SafetyMetric` via `MetricEngine` (`app/evaluation/metrics/implementations/safety_metric.py`); score tracks judge verdict exactly | **Algorithms verified; live judge BLOCKED** |
| Groundedness | **1.0** (grounded), **0.0** (contradicting), explicit **error** when context missing | 0–1 | Eiffel-Tower fixtures: response "330 metres tall" vs "999 metres made of gold" against a fixed context | same judge configuration | injected verdicts {1.0} / {0.0}; judge prompt proven to contain the exact fixture prompt+response+context; 0 judge calls on missing context | `GroundednessMetric` (`…groundedness_metric.py`), `requires_context=true` | **Algorithms verified; live judge BLOCKED** |
| Cost | normalized **1.0 / 0.9895 / 0.8956 / 0.4881 / 0.0 / 0.0** for USD 0 / 0.001 / 0.01 / 0.05 / 0.10 / 1.0 | 0–1 (higher = cheaper) | six `cost_usd` inputs against `DEFAULT_MAX_COST_USD = 0.10` | none (pure calculation) | `CostMetric` (`…cost_metric.py`); formula `1 − log1p(cost)/log1p(0.10)` matches `expected` to floating-point precision; missing `cost_usd` → explicit error (no fabricated score) | log-normalization against the project's documented $0.10 threshold | **Algorithm verified; live usage-based cost BLOCKED** |

Cost provenance recorded per judge call: `cost_usd=3.51e-05`, `cost_estimated=true`
(pricing from `app/providers/cost/defaults.py` for `gpt-4o-mini`), tokens 142/23 —
i.e. the pipeline computes cost from **actual token usage × a named pricing table**,
not a constant.

**Live end-to-end evaluation: BLOCKED.** A fresh real provider attempt on this commit
(`evidence/resume-sprint/provider-metadata-fresh.json`): OpenAI `gpt-4o-mini` reached the
real API and was rejected **HTTP 429 `insufficient_quota` / `credit_balance_exhausted`**;
Anthropic and Groq have **no credential** in this environment. Therefore no live judge
score exists for safety/groundedness, and no live token usage exists for cost. The
scripted judge transport is deterministic test evidence of the algorithms only — it is
not claimed as a live model result, and no number above is presented as model accuracy.

## C. Temporal evidence (fresh, real server)

Fresh real Temporal server on this commit: `temporalio/auto-setup:1.25.0` + PostgreSQL 16
in throwaway containers (`redops-resume-net`, port 57233), production
`EvaluationRunWorkflow` and its production retry policies; only the item-activity bodies
are controlled doubles (deterministic token counts) so no provider call is involved.
Harness: `evidence/harness/verify_temporal.py` (exit 0 both modes).

| Behavior | Test / run | Observed outcome | Artifact |
|---|---|---|---|
| Retry | workflow `redops-verify-retry-20261019-151823` (harness mode `retry`) | Server status **COMPLETED**, result `status="completed"`, `items_completed=1`. Item-activity attempt counter = **2** (attempt 1 failed with the controlled transient error). History: `ActivityTaskStarted` with `attempt=2` and `last_failure.message="controlled transient failure on attempt 1"`, then `ActivityTaskCompleted`; **41 events**. Production policy `maximum_attempts=3`, `initial_interval=2s`, backoff `2.0`. | `evidence/resume-sprint/temporal-retry-summary-fresh.json`, `temporal-retry-history-fresh.json` |
| Cancellation | workflow `redops-verify-cancel-20261019-151856` (harness mode `cancel`) | `cancel` signal recorded at `15:18:57.44Z` mid-run; in-flight item 0 allowed to finish; items 1–2 **never scheduled** (`item_indices_executed=[0]`); run finalized with `status="cancelled"`, `items_completed=1` of 3; server status COMPLETED (graceful cancel); **39 events**. | `evidence/resume-sprint/temporal-cancel-summary-fresh.json`, `temporal-cancel-history-fresh.json` |

Repo test-suite companions (also passing in the 3243 run, test-environment/mocked level,
clearly weaker than the server evidence above):
`tests/infrastructure/temporal/test_b12_1_runtime_reliability.py`
(`test_workflow_has_retry_policy_definitions`, `test_retry_policy_imports`,
`test_agent_loop_retry_is_bounded`) and
`tests/evaluation/temporal/test_activities_workflow.py::TestEvaluationRunWorkflow::test_workflow_cancelled_mid_execution`.

These are **real Temporal server** results, not `WorkflowEnvironment` test-env results.

## D. Limitations

- **Live judge / live evaluation: BLOCKED** — OpenAI credit-exhausted (429); Anthropic and
  Groq keys absent. Safety/groundedness values in §B are algorithm-verification results
  with a scripted judge transport, explicitly not live model scores.
- **Live usage-based cost: BLOCKED** — no completed live call, hence no real end-to-end
  run cost; the cost *calculation* (usage × pricing table → log-normalized score) is
  verified, including per-call provenance on the scripted run.
- Frontend suite required the lockfile fix; before the fix `npm ci` was broken on fresh
  clones (now fixed on `main`).
- The "17 errors" report could not be reproduced; only the wrong-cwd invocation produces
  errors (108, environmental).
- Prior-sprint artifacts (`evidence/*.json` from commit `d437c73…`) were reused only as
  historical context; every number in this report comes from the fresh runs logged in
  `evidence/resume-sprint/` on `4868972…`.

## E. Resume-ready claims

**Conservative (all numbers directly verified):**

> Verified a 3,243-test backend suite (3,243 passed, 3 opt-in skips, 0 failures) and a
> 31-test frontend suite (31 passed, 6 files) on fresh clones of the current main via
> isolated Docker infrastructure; proved Temporal activity retry (2 attempts after a
> controlled transient failure, workflow COMPLETED) and mid-run cancellation (signal
> honored, unscheduled items never executed) against a real Temporal server; verified the
> safety/groundedness/cost metric algorithms (24/24 checks) end-to-end through the real
> MetricEngine/JudgeEngine, and diagnosed the live-judge gap as external
> (OpenAI 429-insufficient_quota; other keys absent) rather than a code defect.

**Stronger (only if a live LLM credential is available to extend the evidence):**

> …and completed a live end-to-end evaluation with real judge responses and
> usage-derived cost accounting across safety, groundedness, and cost metrics.

**Number → evidence map:**

| Number | Evidence artifact |
|---|---|
| 3243 passed / 3 skipped / exit 0 | `evidence/resume-sprint/backend-test-output.txt` (commit `4868972…`) |
| 31 passed / 6 files / exit 0 | `evidence/resume-sprint/frontend-test-output.txt` (fixed tree = lockfile-fix commit) |
| 3231 passed (pre-sprint control) | `evidence/resume-sprint/old-snapshot-43714a5-backend-test-output.txt` |
| 108 errors (wrong-cwd control) | root invocation described in §A (not committed: reproduced ad hoc) |
| 24/24 metric checks; safety 1.0 & 0.1; groundedness 1.0 & 0.0; cost 1.0…0.0 | `evidence/resume-sprint/metric-sanity-check-fresh.json`, `metric-sanity-fresh-output.txt` |
| Retry: attempt=2, COMPLETED, 41 events | `evidence/resume-sprint/temporal-retry-summary-fresh.json`, `temporal-retry-history-fresh.json` |
| Cancel: status=cancelled, executed=[0], 39 events | `evidence/resume-sprint/temporal-cancel-summary-fresh.json`, `temporal-cancel-history-fresh.json` |
| OpenAI 429 insufficient_quota; others no-credential | `evidence/resume-sprint/provider-metadata-fresh.json` |

Claims about model accuracy, production reliability, latency, or percentage
improvements are deliberately **not** made: no measurements back them.
