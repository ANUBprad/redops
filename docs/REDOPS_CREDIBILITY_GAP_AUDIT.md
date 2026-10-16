# RedOps Credibility Gap Audit

**Updated:** 2026-10-16  
**Branch:** `main`  
**Purpose:** Current-state audit of implementation claims, test evidence, and release blockers. This document supersedes the stale August 30 audit below; historical findings are not current truth unless restated here.

## Executive summary

The repository has a substantial implementation and a green backend/frontend CI baseline on the prior audited commit. That does **not** establish metric accuracy, live external-provider success, staging readiness, or complete red-team accounting.

Changes made during the October 16 closure work:
- The semantic judge now controls the red-team `is_violation` decision for definitive `SUCCESS` and `FAILURE` verdicts. An inconclusive or failed judge still falls back to keyword evidence. Regression tests cover both a keyword false-positive refusal and a semantic success without keyword matches.
- The red-team run form now offers OpenAI, Anthropic, and Groq instead of an unsupported Google provider option, with a frontend regression test.
- The bundled synthetic corpus is explicitly marked `is_ground_truth: false`. `scripts/validate_metrics.py` refuses to report accuracy for a corpus not marked as genuine ground truth, and a regression test checks that refusal.
- Gitleaks and container security workflows now trigger for `main` pushes and pull requests. Trivy high/critical findings are configured to fail the image-scan step.
- The README links to this audit and the release checklist.

These are source changes committed to `main`; CI results for the new commits must be checked before describing them as passing. No live-provider or staging run was performed as part of this source-only work.

## 11-claim status

| # | Claim | Current status | Evidence / remaining gap |
|---:|---|---|---|
| 1 | Red-team effectiveness is keyword-only | **Partially fixed** | The production activity wires a semantic judge. The evaluator now lets definitive semantic SUCCESS/FAILURE control `is_violation`; heuristic dimension scores remain supporting evidence. Judge error/INCONCLUSIVE falls back to keywords. Live judge execution is unverified. |
| 2 | No ground-truth dataset | **Still open** | A synthetic fixture corpus exists, but it is explicitly not ground truth. No independent, license-cleared, human-labeled validation corpus is present. |
| 3 | Metrics lack real validation data | **Still open** | Validation loader/runner and a CLI exist. The synthetic corpus is not valid evidence of metric accuracy; the CLI now refuses to score it. No accuracy claim is justified. |
| 4 | Attack generation ignores selected definitions | **Source path fixed; runtime unverified** | Selected IDs now pass API → Temporal input → activity repository lookup → campaign engine, which executes the selected template and fails loudly for missing definitions/templates/variables. Owner-created definitions are checked against the authenticated run owner. A live campaign has not yet verified this path. |
| 5 | Provider execution is not real | **Source path implemented; live use unverified** | Target execution calls the configured provider's `chat()` through the registry. No successful real OpenAI, Anthropic, or Groq call was demonstrated in this audit. |
| 6 | Temporal does not orchestrate real evaluation | **Implemented; live red-team run unverified** | Evaluation and red-team workflows/activities are present and covered by deterministic tests. A fresh running deployment, cancellation, retry, and persistence cycle was not exercised here. |
| 7 | Red-team cost tracking is complete | **Incomplete** | Target calls use `CostCalculator`, but campaign totals/budget accounting do not currently establish full target + judge + mutation cost. Judge usage/cost is recorded on effectiveness; mutation-provider usage is not included in the round total. Unknown pricing must not be interpreted as free. |
| 8 | Multi-provider execution is incomplete | **Source support implemented; live parity unverified** | OpenAI, Anthropic, and Groq adapters exist, and the UI provider option has been corrected. Real requests and model-specific options have not been verified for all three. |
| 9 | Multi-model comparison is implemented | **Source path exists; live comparison unverified** | Comparison APIs and reliability code exist. No fresh live comparison of runs/providers was executed during this audit. |
| 10 | Red-team UI start is broken | **Source defects fixed; full runtime path unverified** | The form sends provider/model and offers OpenAI/Anthropic/Groq. The API returns saved configuration, passes definition IDs and authenticated owner through Temporal, and the detail UI renders persisted round evidence. Browser-to-provider-to-result execution remains unverified. |
| 11 | Red-team results are not persisted | **Persistence implemented; visibility incomplete** | The Temporal activity checkpoints rounds and persists campaign results; the run response includes stored `campaign_results`. The detail UI does not adequately render per-round results, and no dedicated rounds endpoint exists. |

## Detailed technical findings

### Semantic verdicts

The semantic judge is wired in `backend/app/redteam/temporal/activities.py` and used by `AdaptiveCampaignEngine`. The evaluator previously allowed keyword-based flags to contradict a definitive semantic verdict. The October 16 change makes a valid semantic SUCCESS mark an attack as a violation and a valid semantic FAILURE clear the violation flags. Severity remains conservative: semantic success alone does not prove a severe leak. If judging fails or is inconclusive, the evaluator retains the keyword fallback and records the source accordingly.

Files:
- `backend/app/redteam/engine/attack_evaluator.py`
- `backend/tests/redteam/test_semantic_effectiveness.py`

### Cost and budget accounting

`TargetExecutor` uses the shared cost calculator for target token usage. The campaign round's `cost_usd` and budget total are based on target execution cost; semantic-judge cost is recorded separately and mutation-provider cost is not fully represented in the campaign total. Therefore, a displayed campaign total or `max_cost_usd` budget must not be described as an all-in cost cap until all provider calls are accounted for and unknown pricing is tracked separately.

Files:
- `backend/app/redteam/engine/target_executor.py`
- `backend/app/redteam/engine/campaign_engine.py`
- `backend/app/redteam/engine/semantic_judge.py`
- `backend/app/redteam/temporal/activities.py`

### Attack definitions and UI

The form submits `attack_definition_ids`, target provider, and target model. The API passes selected IDs and the authenticated owner into `RedTeamWorkflowInput`; the Temporal activity resolves the persisted definitions, rejects missing/archived or non-owner-created definitions, and passes the templates into the campaign engine. The engine executes the selected template and rejects missing required variables rather than sending unresolved placeholders. The API response now returns saved configuration, and the run detail page renders persisted per-round evidence. These source paths have regression tests, but the browser-to-real-provider-to-database path still requires a live smoke test.

Files:
- `frontend/app/(main)/redteam/runs/new/page.tsx`
- `backend/app/api/redteam.py`
- `backend/app/redteam/temporal/activities.py`
- `backend/app/redteam/engine/campaign_engine.py`

### Result persistence and visibility

Round checkpoints and final `campaign_results` persistence exist in the Temporal activity and repository. Existing persistence tests use deterministic providers and an SQLite test database. The remaining gap is user-facing visibility: the frontend run-detail view does not render the stored round evidence in a useful way, and a dedicated rounds endpoint is not implemented.

### Ground-truth validation

The checked-in corpus is a synthetic schema/pipeline fixture whose labels were designed around the keyword metric. It is not independent ground truth. Its provenance now correctly says `is_ground_truth: false`, and the CLI returns an error rather than printing an accuracy percentage for it. This is a guard against misleading claims, not a completed validation program.

Before claiming metric accuracy:
1. Add independently labeled and license-cleared examples with documented provenance and adjudication.
2. Keep a held-out test split that is not used to tune keyword lists or judge prompts.
3. Run the metric against that corpus and report confusion counts and per-category performance.
4. Add a CI gate that validates corpus provenance and runs regression checks on the approved dataset.

### CI security workflows

The secrets and Docker workflows now trigger for `main` pushes and pull requests as well as `develop`. Trivy is configured to fail on HIGH/CRITICAL findings instead of ignoring scanner exit status. This change is not evidence that the scans have passed: inspect the workflow runs for the current commit and resolve any findings. Real staging checks remain manual release gates.

## Test evidence and limitations

On the previously audited commit `4aa250cc555c1f212a04eaa0653f5d76d6e51007`, GitHub Actions reported:
- Backend: 3,231 passed, 21 warnings; no test failures.
- Frontend: 29 passed across five test files; no test failures.
- Backend/frontend CI jobs were green on that commit.

The closure changes after that SHA have not been locally executed in this environment. They must be validated by CI before their test status is marked passed. In particular, watch for the existing `aiosqlite` background-thread warning in `tests/redteam/test_semantic_effectiveness.py::TestAuditAdaptiveStrategy::test_heuristic_violation_not_counted_as_semantic_success` and the Codecov upload error; neither is a test assertion failure, but both deserve follow-up.

Not verified in this audit:
- Real API calls with valid OpenAI, Anthropic, and Groq credentials.
- A browser-launched red-team run that reaches the target provider and shows stored results.
- Live Temporal cancellation, retry, and duplicate-persistence behavior on a running deployment.
- Staging deployment, rollback drill, Prometheus scrape, Grafana dashboard, and alert firing.
- Successful Trivy/Gitleaks runs on the current post-change commit.

## Release recommendation

**Do not call v0.1.0 production-ready yet.** The implementation and test infrastructure are substantial, but four credibility gaps remain release blockers:

1. Run a live red-team smoke test proving the selected persisted definition becomes the actual target prompt and the stored round is visible in the UI.
2. Campaign accounting is explicitly labeled target-call-only; judge costs are stored separately and mutation-provider usage is not fully included. Full all-provider cost accounting remains open.
3. Confirm the new round-evidence UI against a live persisted campaign.
4. The release checklist must have evidence for real-provider smoke tests, staging deployment, rollback, and monitoring. The synthetic corpus must not be used to claim metric accuracy.

Use the wording **“AI evaluation and red-teaming platform with durable orchestration and documented limitations”** until the live-provider, ground-truth, cost-accounting, and staging gates are demonstrated.
