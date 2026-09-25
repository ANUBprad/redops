# P6-C3 — Red-Team Campaign Round Idempotency: Implementation

Status: DONE. Fixes the round-level retry ambiguity identified at the end
of P6-C2 (the "F-2 red-team whole-campaign retry" durability gap). Changes
in this commit are production + test only; nothing else from P2/P3/P4/P5 or
the P6-A/P6-B forensic findings is touched.

---

## 1. Problem being fixed (the boundary left open in P6-C2)

P6-C2 made each *item* execution retry-idempotent within the evaluation
flow, but explicitly deferred the **red-team whole-campaign** durability
gap to P6-C3. The failure mode: `red_team_campaign_activity` (a Temporal
activity) executes an entire adaptive campaign, and the only in-memory
restart the Temporal layer could give a crashed run was "replay everything
from round 0". A retry therefore re-invoked the target provider, the
mutation provider getter, and the semantic judge **for every completed
round** as well as the incomplete one. That is billable provider churn on
every retry, and it defeats the point of the P6-C2 idempotency work for
campaign-level retries.

`1c7488e` explicitly scoped P6-C2 to items and listed "F-2 (red-team
whole-campaign retry idempotency) → deferred to P6-C3" in its limitations
section. This commit closes F-2.

## 2. Execution flow: before vs. after

- **Before:** `run_campaign` runs rounds 1..n in a plain loop. A worker
  crash / `start_to_close` timeout / process kill anywhere mid-campaign
  discards every completed round's provider work; the Temporal redelivered
  activity re-runs `engine.run_campaign` from an empty state, so providers
  are re-invoked round-by-round from the start.
- **After:** the activity writes each successfully-computed round to a
  durable `red_team_rounds` table as it completes. A redelivered attempt
  loads the persisted rounds, **reconstructs the campaign starting on the
  first incomplete round**, and re-invokes providers only for rounds that
  have no durable record.

## 3. Exact deterministic round identity

A campaign round is identified deterministically by the composite key

```
(attack_run_id, round_number)
```

- `attack_run_id` = `input.attack_run_id`, the stable Temporal workflow /
  activity input that is identical across retries of the same attempt and
  across Temporal-attempt replay.
- `round_number` = `round_.round_number` (1-based), produced in order by
  the engine loop and stable across re-execution because the campaign is
  re-constructed from the persisted run status + role/prompt config, not
  from anything randomized.

No global fabricated identifier was invented: the pair is exactly what the
Temporal scheduler already keys a retry on (a redelivered activity attempt
carries the same `input.attack_run_id`), so same-input + same-round
collide onto one durable row. Distinct runs of the same campaign never
share rounds (each has its own `attack_run_id`).

## 4. Durable checkpoint / persistence mechanism

- New table `red_team_rounds` (migration `022_create_red_team_rounds_table`,
  `down_revision = "021"`) with composite PK `(attack_run_id, round_number)`.
- New `RedTeamRoundModel`
  (`app/infrastructure/database/models/red_team_round.py`), exported from
  `models/__init__.py`.
- New `RedTeamRoundRepository`
  (`app/infrastructure/database/repositories/red_team_round_repository.py`)
  with the durable boundary helpers used by the activity.
- The activity gains four helper functions (`activities.py`):
  - `_durable_round_schema_present()` — schema probe (approximately once per
    activity) deciding whether the durable path is available.
  - `_load_run_status(attack_run_id)` — read only the run status.
  - `_load_durable_rounds(attack_run_id)` — load persisted rounds for the run.
  - `_checkpoint_durable_round(attack_run_id, round_)` — upsert one round
    atomically.
- Serializers `_round_record_to_model` / `_model_to_campaign_round` convert
  between the engine's `CampaignRound` and the DB model (JSON for
  `round_json`; id/scalar columns for the rest).

## 5. How Temporal activity retries behave with this change

- The retry property Temporal already gave (redelivery of the same
  `attack_run_id` input) is now paired with a durable round table: the
  redelivered activity first queries `_load_durable_rounds`.
- Because the composite primary key is `(attack_run_id, round_number)`, a
  provider failure mid-round leaves the round **absent** from the table, so
  the retried attempt is free to call the provider for that round.
- A round that *did* complete and was checkpointed is **present**, so a
  retry never schedules provider work for it.

## 6. How completed rounds are prevented from re-running providers

The only provider side effects in a round are:

1. the **target provider** call (LLM attack response),
2. the **mutation provider** getter (via `mutation.get_mutation`),
3. the **semantic judge** call (effectiveness determination).

All three live inside the round execution that `campaign_engine` runs for a
`CampaignRound`. The engine now accepts `resume_rounds` (rounds already
completed) and `checkpoint_round` (persist-after-success callback):

```python
def __init__(self, ..., resume_rounds=(), checkpoint_round=None): ...
```

When a durable resume occurs the engine's `campaign.start()` is seeded with
the durable rounds; each resumed round is re-injected **in memory** from its
persisted record (domain reconstruction, no provider call), the loop
advances to the first round with no durable record, and only that and
subsequent rounds invoke providers — naturally through the production
`_execute_round` path. There is no separate "skip" flag in the provider
call; preservation is structural: the provider call simply is not executed
because the round is replayed from its record rather than executed.

## 7. How a campaign retry resumes from the first incomplete round

1. Activity loads `resume_rounds` from the durable table.
2. Engine seeds `campaign.start()` with them.
3. The engine loop iterates expected round numbers; for a round index that
   already has a durable "completed" record it replays the in-memory round
   and continues; for the first index with no record it executes
   normally (provider calls).
4. Every newly-completed round is handed to `checkpoint_round` before the
   loop advances, so the durable boundary moves forward one round at a time.

The activity logs `"Resuming red team campaign ... from %d durable
round(s)"` when a resume actually happens (seen in the workflow e2e test).

## 8. How campaign_results are preserved

- `campaign_engine` accumulates `results` across all rounds (resumed +
   freshly-executed), so the final `CampaignResult` the activity returns
   contains the resumed rounds' effectiveness/violations exactly as a
   single uninterrupted run would.
- The whole-campaign workflow (P6-B / P6-C2 handler + `predict_run_workflow`
  e2e) is untouched: the Temporal activity still returns the full
  `CampaignResult`, and completion tallies each round exactly once.

## 9. Interaction with P3-3A / MetricResults

Round-level efficacy, efficiency and safety metrics are computed *per round*
inside the engine and are **not** routed through the `MetricEngine`
item-metric pipeline P3-3A established (that pipeline is the *evaluation*
path). Because the checkpoint happens at the `campaign_engine` boundary and
carries the round id + `round_json`, the durable record contains everything
needed to reconstruct the round's metrics without re-running providers.
The metric-reuse property from P6-C2 (§7) and the provider-failure /
metric-failure semantics from P6-C2 (§8–§9) are preserved unchanged: a
metric failure still recomputes metrics from the durable evidence and never
forces a provider re-call.

## 10. Concurrency / race handling

Temporal guarantees a single active attempt per activity schedule, so two
attempts of the same `attack_run_id` are not genuinely concurrent in normal
operation. Should a racing duplicate write ever occur, the `(attack_run_id,
round_number)` PK + replay convergence make it harmless: any duplicate round
write hits the same PK (updated in place via upsert), and the resumption
reads `resume_rounds` by run id — a completed round replayed from the record
is idempotent by construction. No locks were added (not requested).

## 11. Known unavoidable crash windows

- **Provider → checkpoint window:** a crash between a provider call's
  success and the durable commit of that round leaves the round absent, so
  the retried attempt re-invokes the provider for that single round. This is
  the same unavoidable durability window documented in P6-C2 §11 and is the
  reason the implementation claims *at-least-once per round*, not
  exactly-once. The commit is a single transaction (upsert + commit), so no
  partial/duplicate round row is ever durable.

## 12. Explicit limitations — this is NOT exactly-once

- Per-round execution is **at-least-once**: the provider may run more than
  once only in the single-round crash window above and on genuine provider
  failures (which legitimately must retry).
- It does **not** dedupe across two *distinct* `attack_run_id`s (distinct
  retries of a campaign correspond to distinct runs; Temporal creates the
  run once, so this is moot in practice).
- It does not add DB-level uniqueness beyond the natural composite PK; it
  does not add cross-run dedup, non-UUID id support, or exhaustive-retry
  loss prevention (all still out of scope).

## 13. Every changed file and why

| File | Change |
| --- | --- |
| `backend/app/redteam/temporal/activities.py` | Durable round wiring: `_durable_round_schema_present`, `_load_run_status`, `_load_durable_rounds`, `_checkpoint_durable_round`, serializers, `resume_rounds`/`checkpoint_round` passed into the engine, sentinel re-raise. |
| `backend/app/redteam/engine/campaign_engine.py` | `_RoundPersistenceError` sentinel, `resume_rounds` + `checkpoint_round` init params, `campaign.start()` replay, checkpoint after each successful round. |
| `backend/app/infrastructure/database/models/red_team_round.py` | New `RedTeamRoundModel` (composite PK, id/JSON columns). |
| `backend/app/infrastructure/database/models/__init__.py` | Export `RedTeamRoundModel`. |
| `backend/app/infrastructure/database/repositories/red_team_round_repository.py` | New `RedTeamRoundRepository` (durable boundary helpers). |
| `backend/alembic/versions/022_create_red_team_rounds_table.py` | Migration for `red_team_rounds`; `down_revision = "021"`. |
| `backend/tests/redteam/temporal/test_red_team_round_idempotency.py` | New focused suite (below). |

`agent_loop.py` and `frontend/package-lock.json` were left **unstaged** (pre-existing, unrelated); they are not part of this commit. Ruff's formatter, when run on `activities.py`, touched the already-existing `campaign_engine.py` import block (I001) — the only production-side reshuffle.

## 14–16. Tests added and their behavior

`backend/tests/redteam/temporal/test_red_team_round_idempotency.py` — 9
tests using a recording fake target provider (invocation counter +
deterministic `ChatResponse`) over the production Temporal activity, with a
real in-memory SQLite DB for durability:

- **A** `test_normal_campaign_executes_each_round_once_and_checkpoints` —
  a first attempt runs rounds 1..N, each provider called once, durable rows
  recorded (round ids 1..N).
- **B** `test_retry_after_completed_rounds_does_not_recall_providers` —
  second activity invocation (simulating a Temporal redelivery after a crash)
  resumes from the durable rounds and does **not** re-invoke providers for
  completed rounds; crosses the full durable boundary.
- **C** `test_retry_campaign_result_preserves_completed_rounds` — resumed
  run returns a `CampaignResult` whose round count/violations include the
  completed durable rounds.
- **D** `test_retry_metric_rows_reuse_stable_round_ids` — metric/round ids
  in the resumed result equal the durable round ids across the retry.
- **E** `test_checkpoint_failure_resumes_from_incomplete_round` —
  `_RoundPersistenceError` raised by a flaky checkpoint on round 3 keeps
  only rounds 1–2 durable; the retry resumes from round 3 without re-calling
  providers for 1–2.
- **F** `test_distinct_runs_do_not_reuse_each_other_rounds` — distinct
  `attack_run_id`s never share/reuse each other's durable rounds.
- **G** `test_workflow_checkpoints_rounds_with_durable_schema` — schema
  probe present ⇒ durable path exercised end-to-end.
- **H** `test_legacy_schema_without_rounds_table_falls_back_to_in_memory` —
  no durable table ⇒ unchanged in-memory behavior (providers re-run on
  retry), proving this is purely additive.
- **I** `test_error_round_is_not_checkpointed` — a failed/errored round is
  **not** checkpointed to `red_team_rounds` and therefore remains
  re-executable on Temporal retry. Its error remains present in the
  in-memory `CampaignResult` for the failed activity attempt, but the
  durable checkpoint contains only successful rounds.

## 17–19. Pre-fix vs. post-fix results

- **Pre-fix (production `1c7488e`, repository/activities not yet durable):**
  scenarios A–G failed because retries re-ran providers (0 durable rows, no
  resume path, no `_RoundPersistenceError`, no migration) and only the
  legacy-fallback and error-round tests passed (H, I). 7 focused tests failed
  pre-fix (verified by running the suite against the pre-fix production
  code); 2 passed (H, I — the non-durable behaviors).
- **Post-fix:** same file, production code at `0ff90e0` → **9 passed**.
- Focused run: `9 passed in 7.29s`.

## 20–23. Quality gates

- **Ruff (20):** `ruff check` clean on all changed files after fixing the
  I001 import order in `activities.py`/`campaign_engine.py`; no remaining
  issues.
- **Mypy (21):** `Success: no issues found in 5 source files` (strict,
  repo config) on the production changed scope
  (`activities.py`, `campaign_engine.py`, `red_team_round.py`,
  `red_team_round_repository.py`, `models/__init__.py`).
- **Ruff format (22):** `ruff format` reflowed the 6 changed files;
  `ruff format` clean on all of them.
- **git diff --check (23):** no whitespace errors. Only LF→CRLF autocrlf
  warnings, which are repo-wide.

## 24–26. Regression totals (full backend)

- Red-team suite (`tests/redteam`): **252 passed**.
- Integration + infrastructure (`tests/integration`, `tests/infrastructure`):
  **246 passed**.
- Evaluation suite (`tests/evaluation`): **1399 passed**.
- **Full backend `python -m pytest -q`: 2812 passed** (all prior green +
  the 9 new; no regressions).

## 27–31. Commit, push, verification

- Commit: `fix(redteam): make campaign retries idempotent`, 7 files changed
  (1125 insertions, 8 deletions), staged only the P6-C3 files above
  (never `git add .`).
- Push: rebased locally onto the remote `0.13.10` release commit
  (`8045527 chore(release): 0.13.10`) pushed as
  `8045527..0ff90e0 develop -> develop` (fast-forward, no force).
- Verification: `git rev-parse HEAD` == `git rev-parse origin/develop` ==
  `0ff90e03641ed720c694229d0e6d3b17c605c057`; `match=True`.
- Remote head confirmed: develop → `0ff90e0`.
- No `git add .`, no force push, `opencode.md` / `AGENTS.md` untouched.

## 32. Closing

P6-C3 closes the round-level durability gap that P6-C2 left open, by
checkpointing each completed campaign round to a durable `red_team_rounds`
table and having the Temporal activity resume from the first incomplete
round — so a redelivered attempt never re-invokes providers for already
completed rounds. 9 focused tests prove the round boundary with a recording
provider (scenario B crosses the entire durable resume path), the legacy
non-durable path is preserved untouched (scenario H), and the full backend
remains green (2812 passed). It is deliberately **at-least-once per round**,
not exactly-once (documented window + provider-failure retries), which is
the honest guarantee a work-queue retry model can give. Next phase (P6-C4)
is NOT started.
