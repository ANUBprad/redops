# P6-C1 — Execution Idempotency Forensic Audit

**Audit-only phase. No production code, tests, migrations, or Temporal policies were modified.
The only delivered artifact is this report.** See "Scope".

---

## 1. Scope

Audit idempotency of run execution across four surfaces:

- General evaluation path: `EvaluationRunWorkflow` → `execute_item_activity` →
  `persist_metric_results_activity` → `finalize_run_integrity_activity`.
- Red-team path: `RedTeamWorkflow` → `red_team_campaign_activity` →
  `AdaptiveCampaignEngine` → `_finalize_run` / `_persist_metric_results`.
- Metric/campaign-result persistence layers (`metric_results` table, `attack_runs.campaign_results`).
- Temporal activity retry semantics, workflow-start boundaries, and DB uniqueness.

Explicitly **out of scope** (P6-C1 is read-only): any fix implementation, P7 security/isolation,
P6-D retry UX, live-provider validation, and the P6-B fields classified as Unsupported/deferred
(`attack_definition_ids`, `severities`). Those fields are not idempotency concerns.

## 2. Current baseline

- Branch: `develop`
- HEAD: `14754bfb03777c21bc66b3ffc3d81efd3262ed63` (`docs(redteam): reassess P6-B configuration findings`)
- `origin/develop`: `14754bf` (HEAD == origin/develop)
- `opencode.md` SHA256: `001EB7B2FBE00D22DADB434BC6E27FE2778F4045946E65579996D6B094C0DB06` (unchanged)
- Working tree: pre-existing unrelated changes only (`backend/app/agents/runtime/agent_loop.py`,
  `frontend/package-lock.json`, `opencode.md`; untracked prior audit reports + `AGENTS.md`).
  Nothing was added or altered by this audit.

**Regression check (targeted, audit-only):**

| Suite | Result |
|---|---|
| Idempotency-specific files (`test_semantic_effectiveness_persistence.py`, `test_individual_metric_persistence.py`, `test_evaluation_integrity.py`, `test_evaluation_retry_workflow.py`) | 62 passed |
| Temporal activity/workflow suites (all of `tests/redteam/temporal/` + `tests/evaluation/temporal/`, retry-input persistence, red-team run lifecycle, temporal queue alignment) | 125 passed (superset of the 62) |
| P6-A/P6-B regression (`test_target_generation_parameters.py`, `test_mutation_configuration_fidelity.py`, `test_budget_configuration_fidelity.py`, `test_system_prompt_configuration_fidelity.py`, `test_redteam_lifecycle.py`, `test_redteam_temporal.py`, `test_handlers_lifecycle.py`) | 64 passed (overlaps the 125 in two files, not double-counted) |

P6-A (cancellation / progress / campaign-result persistence) and P6-B (configuration fidelity)
behaviors are confirmed intact by the 64-test regression run.

## 3. Idempotency model

Explicit semantics guard against overclaiming "exactly-once":

- **At-most-once provider execution** requires the side effect to be keyed before the call and a
  system-level dedup at the point of effect. No provider call here carries a request-level
  idempotency key, so **provider execution is at-least-once on any activity retry**.
- **Effectively-once persistence**: delete-then-insert keyed on `(run_id, item_id)`/`(run_id, round_id)`
  makes persistence idempotent *only when both IDs parse as UUIDv7 and the key is stable across
  attempts*. Both conditions fail in the red-team retry path (round IDs are regenerated per attempt).
- **Effectively-once workflow replay**: Temporal event sourcing memoizes completed activity results;
  workflows never re-execute a completed activity on replay. Workflow-internal counters/traces are
  recomputed deterministically.
- **Fifth type — campaign-result JSON** is last-writer-wins overwrite (not durable append).

These are five independent properties: one being satisfied proves nothing about the others.

## 4. General evaluation failure-boundary analysis

Path (`app/evaluation/temporal/workflow.py:254-361`): per item, `execute_item_activity`
(`app/evaluation/temporal/activities.py:412`; `item_retry`, max 3, 120s start-to-close) →
if metrics → `persist_metric_results_activity` (`activities.py:650`; `persist_retry`, max 3) →
`update_progress_activity`. Then `complete_run_activity`/`fail_run_activity` +
`finalize_run_integrity_activity` (`activities.py:713`).

| # | Failure point | Retried? | Double provider/metric calls? | Double metric rows? | Uniqueness / key |
|---|---|---|---|---|---|
| A | Worker dies before `execute_item_activity` starts/load-check | Yes | No | No | — |
| B | Crash during `_load_existing_metrics` (`activities.py:442`, `598`) | Yes | No (check re-run) | No | `(run_id, item_id)` |
| C | Crash during `provider.chat()` inside `ItemExecutor` | Yes | **Yes — provider re-invoked** | No | none; nothing persisted yet |
| D | Crash after provider returns, during metric eval (judge LLM calls) | Yes | **Yes — provider + judge re-invoked** | No | none |
| E | Crash after metrics computed, before activity return | Yes | **Yes** | No | none |
| F | `execute_item_activity` completed; `persist_metric_results_activity` fails (exhausts 3 retries) | Persist retried, then workflow marks `items_failed += 1` | No (execute is memoized) | No | **Result lost — provider billed, metrics never written** |
| G | Persist committed but acknowledgement lost → Temporal re-runs persist | Yes | No | Delete-then-insert prevents duplicates *when both IDs are UUIDv7* | `(run_id, item_id)` |
| H | `update_progress` / `finalize_run_integrity` re-run | Yes | No | No (column overwrite) | run-scoped overwrite |

**Gaps:** C/D/E are genuine double-execution windows (provider + judge billed twice). The
`_load_existing_metrics` guard can never cover them — metrics are persisted only *after* the
activity returns, in a separate activity. Run counters/traces are replay-safe (workflow event
sourcing). F is silent data loss (the item is counted failed after retries, but the paid response is
discarded).

## 5. Red-team failure-boundary analysis

Path: `red_team_campaign_activity` (`app/redteam/temporal/activities.py:367`) runs the **entire**
campaign loop in one activity (`start_to_close` 2h, `RetryPolicy(maximum_attempts=2)` at
`app/redteam/temporal/workflow.py:56-62`). The loop (`campaign_engine.py:117-157`) is purely
in-memory: scenario generation, mutation, target `provider.chat()`, semantic-judge LLM call, and
metric-engine calls per round; **nothing is persisted until the activity's final two steps**
`_finalize_run` (`activities.py:488`) and `_persist_metric_results` (`activities.py:550`).

| # | Failure point | Retried? | Double provider/metric calls? | Cross-attempt state |
|---|---|---|---|---|
| A | Crash during campaign construction / round 1 generation | Yes (only on structural failure — see below) | No | nothing persisted |
| C | Crash mid-loop after any round's LLM calls | Yes (2h start-to-close timeout → retry) | **Yes — the full remaining campaign re-runs; every prior round's target/judge/metric calls are re-invoked with freshly generated prompts** | nothing persisted |
| D | Crash in `_finalize_run`, before commit | Yes | **Yes — full re-run** | prior `campaign_results` not committed |
| E | `_finalize_run` committed; crash before/within `_persist_metric_results` | Yes | **Yes — full re-run** | second attempt's `record_campaign_results` + `persist_campaign_results` **overwrite the JSON**; status guard (`RUNNING` only, `entities.py:395`) skips complete/record_scenario |
| F | All persistence committed; crash before activity ack | Yes | **Yes — full re-run** | **duplicate metric rows accumulate**: delete-then-insert keys on `(attack_run_id, round_id)` and round IDs are fresh UUIDv7 per attempt → attempt-1 rows are never deleted |
| G | Activity acked; workflow replay | No | No | memoized |

Notes:

- The activity wraps everything in `try/except` and **returns** `status="failed"` instead of raising
  (`activities.py:463-474`). So in-process exceptions are *not* retried by the RetryPolicy; only
  worker crashes, timeouts, and process death trigger retries — which is precisely the realistic
  failure mode for a multi-hour campaign.
- Round identity is regenerated on every attempt: `CampaignRound.round_id`, `TargetExecution.execution_id`,
  `AttackEffectiveness.effectiveness_id`, `AttackScenario.scenario_id`, and `AttackLineage.lineage_id`
  all default to a fresh `UUIDv7.generate()` (`app/redteam/domain/campaign.py:96,108,138,179`). No
  stable key survives an attempt.
- Consequences of a retry after partial persistence (E/F): the second attempt **overwrites**
  `attack_runs.campaign_results` with its own rounds, so attempt-1 rounds disappear from the JSON
  payload, while attempt-1 metric rows remain in `metric_results` under round IDs that no longer
  exist in the JSON. Result: silent data divergence plus duplicated metrics per run.

This is effectively **at-least-once at whole-campaign granularity with zero cross-attempt dedup** —
the most expensive idempotency gap in the system.

## 6. Non-UUID item ID analysis (N15)

`execute_item_activity` derives the item key as `item_id = input.item_id or str(item_index)`
(`activities.py:441`). API item IDs are caller-supplied `DatasetItemRequest.id`
(`app/api/evaluation_run.py:80-97`); when absent the key is `"0"`, `"1"`, … .

Both idempotency gates parse the key as UUIDv7 and **silently no-op on failure**:

- `_load_existing_metrics` catches parse exceptions and returns `None` (`activities.py:610-614`)
  — provider dedup disabled for every non-UUID item key.
- `persist_metric_results_activity` catches parse exceptions and **skips the delete**, degrading
  to a plain insert (`activities.py:689-705`) — boundary G then produces duplicate rows.

The `metric_results.item_id` column is `String(36) NOT NULL` (migration `003`, model
`app/infrastructure/database/models/metric_result.py:25`). Any non-UUID `item_id` longer than 36
characters fails at the DB on insert — the persist activity exhausts its 3 retries, the item is
counted failed, the provider call is already billed, and the result is lost (boundary F +
validation gap). No API-side length/format validation precedes execution.

Impact classification: real whenever callers supply non-UUID dataset IDs (imports, agent-run reuse,
CSV payloads); the idempotency machinery silently degrades to zero protection for that run with no
warning signal.

## 7. Temporal retry analysis

- **Activity memoization (workflow replay):** completed activities are never re-executed. This is
  solid and is the primary reason workflow-level counters and trace lists do not double-count. It
  does **not** protect against activity-level retries, which is where the double-pay lives.
- **General eval:** `execute_item_activity` catches all `Exception` and returns `failed`
  (`activities.py:515-522`) → the `item_retry` (max 3) only fires on structural/timeout failures.
  Each retry re-enters the provider call window (boundaries C/D/E). Persistence is a separate
  activity with its own retries — the only layer that is effectively idempotent (and only for UUID
  keys).
- **Red-team:** single 2-attempt mega-activity. Because the activity never re-raises, the retry
  policy is effectively "retry once on worker death"; that one retry duplicates the whole campaign.
- **Cancellation:** general-eval workflow checks `_cancel_requested` per item and issues
  `cancel_run_activity` with `force=True` (`workflow.py:255-276`); red-team uses
  `TRY_CANCEL` + cooperative `activity.is_cancelled` (`workflow.py:87`, `activities.py:441`).
  Neither rewinds provider calls — a cancelled activity that already issued calls has paid for them,
  and a red-team `TRY_CANCEL` during an LLM call may still complete that call.
- **Takeaway:** the provider is called at-least-once with no request key, no persisted
  pre-commit intent, and no check-then-act around the call itself.

## 8. Database constraint analysis

- `metric_results` (`backed by migration 003`, model `metric_result.py:21-62`): PK is integer
  autoincrement; only two **non-unique** indexes (`ix_metric_results_run_metric`,
  `ix_metric_results_run_item`). **No unique constraint** on `(run_id, item_id, metric_name)`.
  All metric dedup is application-level delete-then-insert and is conditional on UUID parsing.
- `evaluation_run` (migration `002`): `String(36)` PK only.
- `attack_run` (migration `006`, model `attack_run.py:17`): `String(36)` PK only;
  `campaign_results` is a plain JSON column added by migration `017`.
- `persist_campaign_results` (`attack_run_repository.py:114-126`) and `_finalize_run`'s
  `record_campaign_results`/`save` are unconditional last-writer-wins overwrites.
- Transaction boundaries: red-team `_finalize_run` commits campaign results in one session
  (`activities.py:507-526`); `_persist_metric_results` commits metric rows in a **separate** session
  (`activities.py:595-606`). A crash between the two leaves the run terminal with campaign JSON but
  no metrics (or vice versa) — no single commit covers the full attempt.

## 9. Workflow-start analysis

- **Evaluation** (`app/api/evaluation_run.py:181-242`): optional `Idempotency-Key` →
  deterministic workflow ID `evaluation-run-idem-{sha16(key)}` (`evaluation_run.py:58-72`).
  Sequential replay returns the existing run. Concurrent replay: both requests can pass the
  `find_by_workflow_id` pre-check and create a run; the first `start_workflow` wins on the unique
  workflow ID; the loser's `start_workflow` raises `AlreadyStarted`, which is **not an app
  `BaseError`**, escapes the handler, and answers 500 — while its freshly created run is left
  stranded in `CREATED` (never queued). No double execution (workflow-ID uniqueness is the real
  backstop), but a leak + 500 on concurrent idempotent re-submission.
- **Red-team** (`app/api/redteam.py:406-466`): workflow ID is `red-team-run-{run_id}`, and the
  `AttackRun` state machine (`entities.py:314-339`) restricts `start()` to `QUEUED`. Sequential
  duplicate start → `ConflictError` → 409. Concurrent duplicate start: the handler re-reads fresh
  state, so the second request observes `RUNNING` and fails with `ConflictError` on `start()`; the
  harmful race requires a read-before-commit window, ending in `start_workflow` raising
  `AlreadyStarted`, which the `except Exception` path routes into `FailAttackRunHandler`
  (`redteam.py:446-463`) — and `fail()` has **no state guard** below the terminal check
  (`entities.py:359-372`), so a `RUNNING` run can be marked `FAILED` while its workflow still
  executes. Narrow, but the run-state corruption is silent (the later `_finalize_run` skips the
  RUNNING-only transitions and merely overwrites `campaign_results`).
- When `start_workflow` fails for a genuine reason, red-team correctly fails the run and returns 502
  (`redteam.py:446-463`) — that path is sound.

## 10. Findings

No ordering/ranking is implied; each finding carries independent classification and priority.
"Current behavior" is what the code does today; "existing protection" is what already limits the
blast radius.

### F-1 Provider execution is at-least-once across activity retries (both paths)
- **Boundary:** C/D/E (general eval); C–F (red-team).
- **Current behavior:** a retried `execute_item_activity` re-invokes `provider.chat()` and any
  judge/metric LLM calls; a retried `red_team_campaign_activity` re-runs the entire campaign with
  freshly generated prompts. Nothing is persisted before the provider call, so the check-then-act
  guard in `_load_existing_metrics` cannot cover the window.
- **Evidence:** `activities.py:441-522`; red-team `activities.py:403-461`; `workflow.py:254-301`.
- **Existing protection:** workflow replay memoization prevents *workflow*-level duplicates; the
  red-team activity suppresses in-process retries by catching all exceptions. Neither protects the
  provider call itself.
- **Remaining risk:** double billing (target + judge + metric calls) proportional to items/rounds,
  triggered by worker crash/timeout.
- **Classification:** Genuine production defect. **Priority:** P1.

### F-2 Red-team whole-campaign duplication with unstable round identity
- **Boundary:** C–F (red-team).
- **Current behavior:** every retry regenerates `round_id`/`execution_id`/`scenario_id`
  (`campaign.py:96,108,138,179`) and overwrites `campaign_results` JSON (`attack_run_repository.py:114-126`)
  while leaving prior attempts' metric rows in place (`activities.py:573-604`). No stable key links
  attempts, so delete-then-insert cannot dedup and prior rounds vanish from the JSON but persist as
  orphan metric rows.
- **Evidence:** `activities.py:488-526` and `550-606`; `entities.py:389-414`.
- **Existing protection:** `_finalize_run`'s RUNNING-only guard prevents status corruption on the
  second attempt; it does not reconcile data.
- **Remaining risk:** full duplicate provider workload, duplicated/divergent metrics, campaign JSON
  that silently drops the first attempt's rounds.
- **Classification:** Genuine production defect. **Priority:** P1.

### F-3 General-eval item persistence lacks a DB uniqueness backstop
- **Boundary:** G.
- **Current behavior:** delete-then-insert is the only dedup and degrades to a plain insert for any
  non-UUID key (`activities.py:689-705`); `metric_results` has no unique constraint
  (`metric_result.py:21-62`). A persist retry after committed-but-unacked insert for a non-UUID item
  yields duplicate rows with no constraint to refuse them.
- **Evidence:** migration `003`; `activities.py:682-708`.
- **Classification:** Partial protection. **Priority:** P2.

### F-4 Red-team metric persistence is idempotent within an attempt only
- **Boundary:** E/F red-team.
- **Current behavior:** delete-then-insert correctly dedups a *re-run of the same persist*, but the
  key `(attack_run_id, round_id)` is not stable across campaign retries, so cross-attempt dedup
  fails. P3-3A protects the retry-of-the-same-persist case (boundary G-style); it does not protect
  full campaign re-execution.
- **Evidence:** `activities.py:573-604`; P3-3A regression
  `test_semantic_effectiveness_persistence.py::J` and `test_individual_metric_persistence.py::test_persist_is_idempotent_for_individual_metrics`.
- **Classification:** Partial protection. **Priority:** P2.

### F-5 Idempotency machinery silently no-ops for non-UUID item IDs
- **Boundary:** B, C/D/E, G (general eval).
- **Current behavior:** any item key that is not a UUIDv7 (absent `item.id`, import keys, long or
  arbitrary strings) disables both `_load_existing_metrics` and the persist delete, with no warning;
  keys > 36 chars fail at the column boundary and discard a billed result.
- **Evidence:** `activities.py:441,598-614,687-705`; `metric_result.py:25`; `evaluation_run.py:80-97`.
- **Classification:** Partial protection (degradation) + Documentation/design issue (undocumented
  column length contract). **Priority:** P2 if non-UUID keys are used in practice, else P3.

### F-6 Workflow-start duplication is already prevented
- **Boundary:** start/replay.
- **Current behavior:** evaluation uses `Idempotency-Key` + deterministic workflow ID with
  `find_by_workflow_id` pre-check (`evaluation_run.py:181-242`); red-team derives the workflow ID
  from the run ID and the state machine blocks re-start (`entities.py:314-339`). Temporal workflow
  ID uniqueness is the enforcement point.
- **Remaining risk:** two robustness gaps — (a) *concurrent* evaluation re-submission with the same
  key can strand a second, orphaned `CREATED` run and surface a 500 (`EvaluationRunWorkflow.already
  started` escapes the `BaseError` handler); (b) the red-team parallel-start race can mislabel a
  `RUNNING` run `FAILED` because `fail()` lacks a RUNNING guard (`redteam.py:446-463`,
  `entities.py:359`).
- **Classification:** Existing protection sufficient (duplication prevented); the two edge effects
  are minor robustness issues. **Priority:** not a defect for duplication; P3 for the edge effects.

### F-7 Silent result loss when persistence retries are exhausted (general eval)
- **Boundary:** F.
- **Current behavior:** after 3 persist-attempt failures the workflow counts the item failed and
  drops the already-paid response/computed metrics — no partial-write, no requeue.
- **Classification:** Genuine production defect (data loss; but bounded and retry-scoped).
  **Priority:** P2.

## 11. What P3-3A already solved

- Per-item metric persistence carrying `run_id`/`item_id` metadata onto each `MetricResult`
  (`metric_result_repository.py:71-83`), for general-eval items **and** red-team rounds
  (`activities.py:579-590`).
- Idempotent execute guard: `_load_existing_metrics` returns a reconstructed cached result instead
  of re-calling the provider when `(run_id, item_id)` already has rows — **valid for UUIDv7 item IDs
  only** (`activities.py:598-646`).
- Idempotent persist: delete-then-insert keyed on `(run_id, item_id)` in both the general-eval and
  red-team persist activities (`activities.py:685-708`, `595-604`).
- Proven by the passing regression suites: `test_semantic_effectiveness_persistence.py`,
  `test_individual_metric_persistence.py`, `test_evaluation_integrity.py`.

Ceiling of P3-3A, confirmed by this audit: it protects the persistence/ac knowledge boundary
(covered in boundaries G and within-attempt red-team), **not** the provider-call boundary, not
cross-attempt red-team (round IDs regenerate), not non-UUID keys, and provides no DB constraint.

## 12. Recommended P6-C implementation scope

Smallest confirmed units, in dependency order. **No code shipped here; these are the candidates the
fix phase should size.**

1. **Stable red-team round identity (F-2).** Derive `round_id` deterministically from
   `(attack_run_id, round_number)` (or reuse the run's existing counter) instead of a fresh
   `UUIDv7.generate()`; this makes delete-then-insert dedup work across attempts and keeps
   `campaign_results` merges consistent.
2. **Single-commit red-team persistence (F-2/F-4).** Fold `_persist_metric_results` into the
   `_finalize_run` session so campaign JSON + metric rows commit together, and make the persist
   conditional on the round ID actually being recorded in the attempted campaign.
3. **DB uniqueness backstop (F-3).** Add a unique constraint on `metric_results(run_id, item_id,
   metric_name)` and convert the persist to an upsert (INSERT … ON CONFLICT), removing reliance on
   the UUID-parse gate.
4. **Normalize the item key (F-5).** Key idempotency on a canonical hash of `(run_id, item_index,
   logical item key)` so non-UUID and absent `item.id` entries are covered; add an item_id length
   cap at the API boundary.
5. **Handle exhausted-persist loses (F-7):** on persist failure after retries, mark the run for a
   resume/requeue rather than discarding the provider-paid result — or accept and document the
   bounded loss.
6. **Provider-call dedup (F-1) is the only component requiring a product/provider decision.** The
   effect with an in-flight window and no request key is only recoverable by provider-side
   idempotency (request ID) or deterministic replay of the exact prompt+params. Set the ceiling
   expectation: persistence can reach effectively-once; provider execution reaches at-most-once only
   with a provider key.

`ponytail:` note — F-1's window is structural-crash-only in general eval (the activity suppresses
retries) and worker-death-only in red-team; the fix cost is dominated by stable identity + atomic
persist, not by provider dedup.

## 13. Out of scope (kept for later phases)

- P7: security and isolation of run execution.
- P6-D: user-facing retry UX (the `/runs/{id}/retry` path already creates a fresh run + unique
  workflow ID — `evaluation_run.py:323-359`).
- P6-B Unsupported/deferred configuration fields (`attack_definition_ids`, `severities`).
- Live-provider validation (mock/emulated providers only; no live API calls during this audit).

## 14. Limitations

- Deterministic behavior was verified with the repository's fake providers and in-memory
  Temporal test harnesses only; no live external provider calls were made.
- Retry behavior at the Temporal-server boundary (ack-loss, heartbeats under real failure) is
  reasoned from SDK semantics, not reproduced against a real server.
- Concurrent-start race conclusions (F-6) are derived from code paths under a single-node SQL
  store; lock/versioning behavior on Postgres may differ slightly in the edge window.
- Metrics/rows were reasoned from schema + code; no production data was touched or inspected.

---

**AUDIT ONLY — NO PRODUCTION IMPLEMENTATION COMPLETED.**