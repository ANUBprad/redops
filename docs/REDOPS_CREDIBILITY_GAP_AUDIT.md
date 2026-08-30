# RedOps Credibility Gap — Forensic Audit

**Date:** 2026-08-30
**Branch:** `develop`
**Type:** Forensic audit only — no implementation changes
**Scope:** Determine which claims in the external assessment (2026-08-28, rated 6.5/10) remain true in the current repository versus what has already been resolved by subsequent development.

---

## 1. Executive Summary

The external assessment rated RedOps 6.5/10 and identified six credibility gaps. That assessment was based on an earlier snapshot. Since then, a large amount of development has landed: provider/integration improvements, **Groq provider support**, Docker/Temporal fixes, frontend CSP and production-rendering fixes, endpoint contract fixes, authentication hardening, OAuth CSRF validation, Redis-backed rate limiting, notification org_id propagation, and a large, green test suite.

This forensic audit traced the **real execution paths** (API → Temporal → provider → model → metric/judge → persistence → result) and classified each report claim as still true / partially true / already fixed / inaccurate.

**Headline findings:**

1. **The most serious claim in the report — "red-team execution does not actually call configured LLM providers" — is now FALSE.** `TargetExecutor` resolves providers through the shared `ProviderRegistry` and calls `provider.chat(...)` (`target_executor.py:46,60`), which reaches real OpenAI/Anthropic/Groq HTTP clients when API keys are configured. The red-team Temporal activity receives the real registry via `configure_redteam_provider_registry` (`services.py:276`).

2. **"Temporal does not orchestrate real LLM evaluation" is now FALSE for the general evaluation path.** `EvaluationRunWorkflow` (`evaluation/temporal/workflow.py`) drives `execute_item_activity` → `ItemExecutor` → real `provider.chat()` → real `MetricEngine`/`JudgeEngine`, with SQLAlchemy persistence (`activities.py:407-517`).

3. **However, several report claims remain TRUE for the red-team subsystem specifically:**
   - Attacks are still **hardcoded Python templates** (`redteam/engine/categories.py`), and it is the production path.
   - Red-team *effectiveness evaluation* is still **keyword-based only** in production: `AdaptiveCampaignEngine(registry=registry)` (`redteam/temporal/activities.py:176`) constructs `AttackEvaluator(None, (), None)` (`campaign_engine.py:54`), so the semantic LLM judge and MetricEngine are **never wired** in production. `evaluation_source` is always `"keyword_heuristic"`.
   - Red-team **cost tracking is incomplete**: `TargetExecutor` hardcodes `cost_usd=0.0` (`target_executor.py:75`), so campaign cost accounting is not real.

4. **The ground-truth validation gap is REAL and unresolved.** There is **no ground-truth/labeled evaluation dataset anywhere** in the repository. "Correctness" is proxied by an LLM judging against a free-text reference; there is no objective correctness label, no annotation pipeline, no train/dev/test separation. This is the largest remaining credibility risk and is independent of all the infrastructure work that has landed.

5. **The red-team keyword safety metric hardcodes confidence `0.8`** for every dimension result regardless of evidence (`redteam/metrics/safety.py:67`) — a fabricated confidence constant, not derived from anything.

6. **Real end-to-end execution with an external LLM has not been demonstrated in this audit** because no real API credentials are present in the environment (the `.env` file contains placeholder key stubs, not usable values). All provider-boundary tests substitute in-memory fake/deterministic providers. The production code path is real, but live third-party invocation remains unverified here.

**Bottom line:** RedOps is considerably more credible than the report's implied snapshot — the provider layer, Temporal orchestration, and real-LLM execution are genuinely implemented. The remaining credibility gap is concentrated in **metric correctness validation (no ground truth)**, and in the **red-team subsystem's keyword-only evaluation and inert results persistence**.

---

## 2. Report-vs-Current-Code Comparison

Every item in the roadmap's diagnosis was re-checked against current code.

| External assessment claim | Classification | Evidence |
|---|---|---|
| 1. Safety metrics are merely keyword matching | **B — PARTIALLY TRUE (red-team) / C — FIXED (general eval)** | Red-team production path is keyword-only (`redteam/engine/attack_evaluator.py:49,200-205`, `activities.py:176`). The general `evaluation/metrics` subsystem has 11 LLM-judge metrics that genuinely call a real LLM (`llm_judge_base.py:96` → `judge/engine.py:184`). |
| 2. Safety metrics have no ground-truth validation | **A — TRUE** | No ground-truth/labeled dataset exists anywhere (confirmed by exhaustive search). |
| 3. Metric implementations lack meaningful evaluation datasets | **A — TRUE** | Only `evaluation/data` item loader + a test-only `canonical_items`/golden fixture. No labeled dataset. |
| 4. Red-team attack generation uses hardcoded templates | **A — TRUE** | `redteam/engine/categories.py:14-67` hardcoded dicts; production path (`campaign_engine.py:167-186`). LLM mutation is unreachable (see §8). |
| 5. Red-team execution does not actually call configured LLM providers | **C — FIXED** | `target_executor.py:46,60` calls `registry.resolve(provider).chat()`; registry shared into red-team activity (`services.py:276`). |
| 6. Temporal does not orchestrate real LLM evaluation | **C — FIXED (general eval) / B — partial (red-team)** | `evaluation/temporal/workflow.py` + `activities.py:407` drives real execution. Red-team uses a single Temporal activity too. |
| 7. Cost/token tracking is missing | **B — PARTIALLY TRUE** | Tokens tracked throughout; main eval cost estimated via `CostCalculator` (`item_executor.py:213`). But red-team cost hardcoded `0.0` (`target_executor.py:75`); unknown-provider pricing → `0.0` (`judge/engine.py:240-270`). |
| 8. Multi-provider execution is incomplete | **C — FIXED** | OpenAI, Anthropic, **Groq** via common `BaseProvider`/`ChatProvider` abstraction + `ProviderRegistry`; key-gated registration (`container.py:320-335`). |
| 9. Multi-model evaluation is missing | **C — FIXED** | `reliability/comparison.py::compare_models` + `analytics/api/router.py:452` `GET /analytics/comparison`; tests in `test_model_comparison.py`. |
| 10. End-to-end evaluation is not actually executable | **C — FIXED (general eval) / B — partial (red-team UI)** | General eval: POST `/runs` → Temporal → real provider → persist → GET results all wired. Red-team: UI sends empty `configuration` (`frontend/.../runs/new/page.tsx:34`) → empty `target_provider` → ValidationError; API path works only if provider/model supplied directly. |
| 11. Evaluation results cannot be trusted/reproduced | **B — PARTIALLY TRUE** | Reproducibility infra exists (`reliability/provenance.py, fingerprint.py, accounting.py`), but no ground truth means scores have no correctness anchor. |
| 12. Existing tests provide no evidence about real evaluation quality | **D — INACCURATE / PARTIALLY TRUE** | 144 red-team + 1303 eval/integration tests pass, covering workflow orchestration, metric determinism, judge second-call behavior. BUT no test calls a real provider (all fake/deterministic substitutes) and none validates metric accuracy against ground truth. |

---

## 3. What Is Already Fixed

These report concerns have been resolved in current code:

- **Real provider execution exists.** `ProviderRegistry.resolve(...).chat(...)` reaches the real OpenAI/Anthropic/Groq SDKs (HTTPS). Both the general evaluation path (`evaluation/temporal/activities.py:407-517`) and the red-team path (`redteam/engine/target_executor.py`) use it.
- **Temporal orchestrates evaluation.** `EvaluationRunWorkflow` (`evaluation/temporal/workflow.py`) runs the queue→start→per-item execute→persist→finalize lifecycle. Red-team uses `RedTeamWorkflow` → `red_team_campaign_activity`.
- **Multi-provider support including Groq.** `GroqProvider` reuses the existing OpenAI wire-format client/adapters correctly (`providers/groq/provider.py`), no parallel SDK path.
- **Multi-model comparison.** `GET /analytics/comparison` + `reliability/comparison.py`.
- **Metric engine with tiers:** 9 deterministic, 3-4 embedding-backed, 11 LLM-judge-backed metrics that reach real LLM/embedding providers at runtime.
- **Persistence and API exposure** of metric results via SQLAlchemy and `/metrics/runs/{id}/results`, `/scores`, `/replay` report endpoints.
- **Operational hardening** (security fixes, CSP, rate limiting, OAuth CSRF, org_id propagation) — all unrelated to the metric-credibility gap but improve trustworthiness of the platform.
- **Safety**: the growling-judge "semantic effectiveness" capability is fully built (`redteam/engine/semantic_judge.py`) and heavily tested, but **not wired into the production red-team path** (see §8).

---

## 4. What Remains Genuinely Broken or Incomplete

Ranked by severity:

1. **No ground-truth validation dataset (P0).** No labeled data, no annotation pipeline, no expected scores. Metric correctness cannot be demonstrated. This is the core credibility gap identified by the report and it is **unchanged**.
2. **Red-team effectiveness evaluation is keyword-only in production (P0).** `AdaptiveCampaignEngine(registry=registry)` → `AttackEvaluator(None, (), None)` → `evaluation_source="keyword_heuristic"`. The semantic LLM judge (which would fix this) is never passed in the Temporal activity. Meanwhile the keyword metric hardcodes `confidence=0.8` (`safety.py:67`).
3. **Red-team results are not fully persisted (P1).** `persist_campaign_results` (`attack_run_repository.py:114`) has **zero callers**; per-round prompts/responses/effectiveness are not written; `campaign_results` column exists (migration 017) but is unused. Domain events are never published for the red-team flow.
4. **Red-team cost accounting is fake (P1).** `TargetExecutor` hardcodes `cost_usd=0.0`; campaign budget/cost reporting is therefore not real.
5. **Red-team LLM-based attack generation is unreachable (P1).** `MutationEngine._prompt_variation` falls back to hardcoded suffixes because no `llm_provider` is ever supplied.
6. **Red-team frontend run-start is broken (P1).** The "New Attack Run" form posts `configuration: {}` → empty `target_provider`/`target_model` → `ValidationError` → failed run.
7. **Synchronous HTTP metrics path drops confidence/cost/version (P2).** `ScoreItemHandler` (`evaluation/application/handlers.py:82-96`) and all `api/metrics.py` response builders omit `confidence`/`cost_usd`/`version`, so they serialize as 0 despite being in schema/DB.
8. **Groundedness metric mislabeled (P3).** Declares `HEURISTIC` but is embedding-backed (behavior/metadata mismatch).
9. **Live external-provider invocation never tested (runtime verification gap).** All tests substitute fake providers. Needed before claiming full end-to-end is proven with a real API.

---

## 5. Actual End-to-End Architecture

### 5.1 General evaluation (real, production path)

```
POST /api/v1/runs                                  evaluation_run.py:164
├─ CreateEvaluationRunHandler                      run_handlers.py:44 (persists EvaluationRun)
└─ temporal_client.start_workflow(EvaluationRunWorkflow)  evaluation_run.py:214

Temporal worker (services.py:369-384)
└─ EvaluationRunWorkflow.run                       evaluation/temporal/workflow.py:170
   ├─ queue_run_activity / start_run_activity      activities.py:298,311
   ├─ per item:
   │   ├─ execute_item_activity                    activities.py:407
   │   │   ├─ registry.resolve(provider_name)      activities.py:452  ← REAL registry
   │   │   ├─ ItemExecutor.execute                 execution/item_executor.py:122
   │   │   │   └─ provider.chat(messages, ...)     item_executor.py:149  ← REAL LLM
   │   │   │       (OpenAI/Anthropic/Groq SDK → HTTPS, key-gated)
   │   │   └─ _evaluate_metrics                    activities.py:514
   │   │       └─ MetricEngine.evaluate_batch      metrics/engine.py:163
   │   │           ├─ LLMJudgeMetric.evaluate      llm_judge_base.py:55
   │   │           │   └─ JudgeEngine.judge        judge/engine.py:54
   │   │           │       └─ provider.chat(...)   judge/engine.py:184  ← 2nd REAL call
   │   │           └─ EmbeddingMetric.evaluate     embedding_base.py (provider.embed)
   │   ├─ persist_metric_results_activity          activities.py:639 (SQLAlchemy)
   │   └─ update_progress_activity                 activities.py:331
   ├─ complete/fail_run_activity                   activities.py:356/369
   └─ finalize_run_integrity_activity              activities.py:702 (verdict/provenance/fingerprint)

GET /runs/{id}                          evaluation_run.py:273
GET /metrics/runs/{id}/results|scores    metrics.py:186,228
GET /runs/{id}/events (SSE)              api/observability.py
GET /replay/... (reports)                api/replay.py
GET /analytics/comparison (multi-model)  analytics/api/router.py:452
```

**Configuration required:** a provider API key (`OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/`GROQ_API_KEY`) so the provider is registered (`container.py:320-335`). Without a key, the provider is absent and resolution fails.

**Mocked?** No — this is the real path. Fake providers exist only under `backend/tests/`.

**Failure behavior:** `execute_item_activity` catches exceptions and returns a `failed=True` result (no fabricated score); judge/metric failures return `error`-tagged results excluded from aggregation; run lifecycle has explicit fail/cancel paths.

### 5.2 Red-team (partially real)

```
POST /api/v1/redteam/runs                           api/redteam.py:341
POST /api/v1/redteam/runs/{id}/start               api/redteam.py:404
└─ temporal_client.start_workflow(RedTeamWorkflow)  api/redteam.py:423

RedTeamWorkflow.run (redteam/temporal/workflow.py:33)
└─ red_team_campaign_activity                      redteam/temporal/activities.py:133
   ├─ _get_provider_registry()                     activities.py:153  ← REAL registry
   ├─ AdaptiveCampaignEngine(registry=registry)    activities.py:176
   └─ engine.run_campaign(campaign)                campaign_engine.py:73
       loop per round:
         generate (hardcoded template)             campaign_engine.py:167-186
         mutate (hardcoded suffixes)               mutation.py
         TargetExecutor.execute → provider.chat()  target_executor.py:46,60  ← REAL LLM
         AttackEvaluator.evaluate                  attack_evaluator.py:42
           keyword safety (only; judge/metric=None)
```

**Persistence gap (P1):** the `AttackRun` row lifecycle + config persists, but per-round campaign results are never written and domain events never published.

---

## 6. Metric Architecture Assessment

Three tiers exist in `evaluation/metrics` (`implementations/__init__.py:50-77`):

| Tier | Metric(s) | Provider | Deterministic |
|---|---|---|---|
| Heuristic/rule | cost, latency, token_usage, json_validity, regex_validation, schema_validation, response_length, tool_call_correctness | none | yes |
| Embedding | answer_relevance, context_relevance, semantic_similarity, (groundedness — **mislabeled heuristic**, actually embedding) | `provider.embed` | yes (given embeddings) |
| LLM-judge | correctness, faithfulness, hallucination, instruction_following, reasoning_quality, coherence, safety, bias, toxicity, prompt_injection, jailbreak | `provider.chat` via JudgeEngine | no (stochastic LLM) |

**Confidence semantics:** LLM-judge metrics use LLM-provided confidence (bounded [0,1]); deterministic metrics correctly leave 0.0; errors/parse-failures set 0.0 (no fabricated scores). **Exception:** red-team keyword `safety.py:67` **hardcodes `confidence=0.8`** for every dimension — this is the one fabricated confidence value.

**Ground truth:** none. Reference-based metrics (`correctness`, `semantic_similarity`) compare against a caller-supplied free-text `reference`, but there is no objective correctness label, no answer key, no annotation pipeline, and no stored dataset.

**Persistence:** metric results persist to `metric_results` table via the Temporal path (including `confidence`, `version`, `cost_usd`). The synchronous HTTP path (`ScoreItemHandler`, `api/metrics.py` builders) drops these fields (P2).

**Reproducibility:** provenance/fingerprint/accounting infra + golden test suite exist, but no ground-truth accuracy measurement.

---

## 7. Provider Architecture Assessment

- **Supported providers:** OpenAI, Anthropic, Groq — via a clean `BaseProvider` + capability contracts (`ChatProvider`, `EmbeddingProvider`, `StreamingProvider`, `ToolCallingProvider`, `ReasoningProvider`).
- **Registry:** `ProviderRegistry` (`registry/registry.py`) — register/resolve/discover/health. Sole entry point per opencode.md rule.
- **Groq correctness:** `GroqProvider` correctly composes the existing `OpenAIClient` + OpenAI adapters, pointed at Groq's OpenAI-compatible endpoint (`providers/groq/provider.py`). It correctly omits embedding capabilities (Groq has no embeddings). This is a compliant reuse of the existing architecture, not a parallel SDK path.
- **API-key handling:** keys read from env via `AppConfig` (`core/config.py:95-97`); provider registered only if key present (`container.py:320-335`). No secrets in code; `.env` git-ignored.
- **Timeout/retry:** runtime layer (`providers/runtime/retry`, `timeout`, `circuit_breaker`, `rate_limit`, `fallback`) — comprehensive.
- **Token usage / cost:** token usage extracted from responses; cost via `CostCalculator` with pricing defaults. Unknown provider/model → `0.0` (incomplete accounting, not fabricated). **Red-team `TargetExecutor` hardcodes `cost_usd=0.0`** (P1 gap).
- **Error handling:** typed exceptions (`exceptions/`), error-tagging in metrics/judge; no fabricated scores on failure.

---

## 8. Red-Team Architecture Assessment

- **Attack generation = hardcoded templates (P0/P1).** `redteam/engine/categories.py:14-67` contains ~25 hardcoded prompt dicts; the campaign loop uses `template={}, parameters={}` (`campaign_engine.py:175-176`), so only the **first template per category** is reachable and **placeholders like `{message}` are never substituted** (sent literally to the target model).
- **LLM-based generation is dead code:** `MutationEngine._prompt_variation` (`mutation.py:291-330`) is the only LLM-mutation path, but no `llm_provider` is ever supplied; it silently falls back to hardcoded suffix lists. `AdaptiveRefiner` is pure statistics.
- **Execution is real:** `TargetExecutor` reaches real providers (§5.2).
- **Evaluation is keyword-only in production:** `AttackEvaluator(None, (), None)` (via `campaign_engine.py:54`). The **semantic LLM judge is fully built and tested** (`semantic_judge.py`) but **never wired** into the Temporal red-team activity. `evaluation_source` is therefore always `"keyword_heuristic"` in production.
- **Persistence:** run/definition rows persist; campaign **results do not** (`persist_campaign_results` has zero callers); domain events not published.

---

## 9. Ground-Truth Validation Requirements

This phase does **not** create a dataset. It defines what the repository must support for legitimate metric validation (per the report's roadmap step 1).

**Metric(s) to validate first (recommended order):**
1. **Safety (evaluation) `/ safety (red-team keyword)** — the headline credibility concern; binary in nature but currently keyword-heuristic.
2. **Correctness** — the most-used quality metric; needs objective labels.
3. **Faithfulness / Hallucination** — need factual grounding labels.
4. **Jailbreak / Prompt Injection** — security-critical.
5. Deterministic metrics (JSON validity, schema, latency, token usage, cost) are self-verifying and need no ground truth.

**Labels / categories appropriate:**
- For safety/jailbreak/prompt-injection: **binary safe/unsafe is necessary but not sufficient** — a 3-class (SAFE / SUSPICIOUS / VIOLATED) or 4-class (+LEAKED) label aligned with `SafetyVerdict` is more useful. A `severity` (low/med/high) and a `category` (harm, data-lds, tool-misuse, injection) are appropriate.
- For correctness/faithfulness: a graded scalar (0-1 or 0-5) or a small ordinal (wrong / partial / correct).

**Fields needed per labeled item:** `prompt`, `response` (model-under-test output for judge/red-team validation) **or** `prompt` + `reference` (gold answer) + `context` (for RAG-style metrics), plus `metric_name`, `expected_label` / `expected_score`, `human_labeler_id`, `label_confidence` (low/med/high), `provenance` (source/license), `notes`, `dataset_version`, `split` (train/dev/test).

**Where validation data should live:** a versioned, git-tracked directory (e.g. `datasets/validation/`) with one file per metric or a unified manifest, **separate from** test fixtures and from `scripts/sample_data/`. Loaded lazily, never baked into product code.

**Provenance/licensing:** record source, license (e.g., CC/MIT/Public domain), citation, and whether the data may be redistributed. Never fabricate provenance.

**Train/dev/test separation:** an explicit `split` field or a split manifest; the **dev/test splits must be held out** and never touched during metric tuning. Use stratified splitting by label distribution.

**Avoiding evaluator leakage:** validation items must not appear in the prompt templates, system prompts, or any code path; log-transform/inject only via the dataset loader. Pin dataset version; record it in every validation run's provenance.

**Human labels and confidence:** store labeler id, binary + optional graded label, and a per-label confidence; evidence of disagreement resolution (2-labeler adjudication or majority vote) recorded.

**How metrics should be measured:** for binary metrics — accuracy, precision, recall, F1, MCC, plus confusion matrix. For graded/scalar — MAE, RMSE, Pearson/Spearman correlation, and calibration (binned reliability). For safety verdicts — agreement with human verdicts (Cohen's kappa / Fleiss). Always report on held-out dev/test, not training data.

**Statistical/reporting methodology:** report point estimates **with** confidence intervals (e.g., bootstrap / Wilson for proportions). State n per class. Report per-category breakdowns. Compare against a stated baseline (e.g., random, or "no-judge heuristic"). Do **not** report a single cherry-picked accuracy.

**Preventing fabricated/hand-picked results:** validation must be (a) run by a script that reads the pinned dataset directly, (b) produce a machine-readable report, (c) not allow the metric implementation to be modified between validation runs, and (d) reject results whose provenance/fingerprint does not match the recorded metric version + dataset version. Any claimed number must trace to an actual executed validation run.

**Explicit constraint honored here:** no fake expectations, no made-up 79%/80% figures, and no claim that a metric is validated until real ground-truth data has actually been evaluated.

---

## 10. Risk-Ranked Backlog

Legend: **P0** = blocks credibility or correctness · **P1** = important for production/personal use · **P2** = valuable enhancement · **P3** = polish/future work.

### P0-1 — Build a ground-truth validation dataset & pipeline
- **Problem:** No labeled data exists; metric correctness cannot be demonstrated.
- **Evidence:** No dataset/annotation path anywhere (this audit, §2 claim 2/3, §6).
- **Affected files/modules:** new `datasets/validation/`, new `scripts/validate_metrics.py`, `evaluation/reliability/` (extend provenance/accounting).
- **Dependencies:** none.
- **Scope:** dataset schema + loader + first labeled corpus (start: safety binary + correctness) + validation runner producing a report with CIs.
- **Tests:** loader schema tests; a small signed-sample self-check (not a claim of accuracy).
- **Runtime verification:** run validation script against held-out split.
- **Definition of done:** a committed, versioned, provenance-documented dataset with train/dev/test split **and** a scripted validation run that produces an audit-trail report of measured metrics. (This is the report roadmap's step 1 + 2.)

### P0-2 — Wire the semantic LLM judge + MetricEngine into the red-team production path
- **Problem:** Red-team effectiveness is keyword-only in production; hardcoded `confidence=0.8`; `evaluation_source` always `"keyword_heuristic"`.
- **Evidence:** `redteam/temporal/activities.py:176` → `campaign_engine.py:54` → `AttackEvaluator(None,(),None)`; `safety.py:67`.
- **Affected modules:** `redteam/temporal/activities.py`, `redteam/engine/campaign_engine.py`, `redteam/engine/attack_evaluator.py`.
- **Dependencies:** none blocking (semantic judge already exists and is tested).
- **Scope:** pass a `SemanticEffectivenessJudge` (built from the configured judge provider) and a MetricEngine into `AdaptiveCampaignEngine` in the activity.
- **Tests:** extend `test_campaign_engine.py` to assert `evaluation_source` is `semantic_judge` when wired.
- **Runtime verification:** run a live red-team campaign against a configured provider.
- **Definition of done:** production `evaluation_source` becomes `semantic_judge` (not keyword-only) and the `safety.py` hardcoded confidence is removed/replaced with a derived value.

### P1-1 — Persist red-team campaign results
- **Problem:** per-round results never written; `persist_campaign_results` has zero callers; domain events unpublished.
- **Evidence:** `attack_run_repository.py:114-126` (no callers); migration 017.
- **Affected modules:** `redteam/temporal/activities.py`, `redteam/application/handlers.py`, `attack_run_repository.py`.
- **Dependencies:** none.
- **Scope:** call `persist_campaign_results` from the activity; publish domain events; expose results via API.
- **Tests:** repository + handler persistence tests.
- **Runtime verification:** run a red-team campaign, verify rows.
- **Definition of done:** per-round prompts/responses/effectiveness/semantic data persist and are retrievable.

### P1-2 — Fix red-team cost tracking
- **Problem:** `cost_usd=0.0` hardcoded; campaign cost/budget report not real.
- **Evidence:** `target_executor.py:75`.
- **Affected modules:** `redteam/engine/target_executor.py`.
- **Dependencies:** none.
- **Scope:** extract cost from the provider response or estimate via `CostCalculator`, mirroring `ItemExecutor._estimate_cost`.
- **Tests:** unit test asserting cost reflects tokens.
- **Runtime verification:** live run shows nonzero cost.
- **Definition of done:** campaign cost/budget accounting reflects real usage.

### P1-3 — Fix red-team frontend run-start
- **Problem:** "New Attack Run" posts `configuration: {}` → empty provider/model → ValidationError → failed run.
- **Evidence:** `frontend/app/(main)/redteam/runs/new/page.tsx:34`; `api/redteam.py:422-436`; `campaign.py:323-330`.
- **Affected modules:** `frontend/.../runs/new/page.tsx`, `api/redteam.py`.
- **Dependencies:** none.
- **Scope:** collect `target_provider`/`target_model` in the form and forward into configuration.
- **Tests:** frontend test/type check; backend accepts the payload.
- **Runtime verification:** start a run from UI.
- **Definition of done:** a run can be started end-to-end from the UI.

### P1-4 — Enable (optionally) LLM-based attack mutation
- **Problem:** `MutationEngine._prompt_variation` never receives a provider; generation is hardcoded.
- **Evidence:** `mutation.py:291-330`; no construction site passes `llm_provider`.
- **Affected modules:** `redteam/engine/campaign_engine.py`, `mutation_selector.py`, `mutation.py`.
- **Dependencies:** P0-2 (provider wiring) to reuse infrastructure.
- **Scope:** pass a provider for mutation; keep suffix fallback.
- **Tests:** LLM-variation path with a fake provider; fallback tested.
- **Runtime verification:** live run generates a variation.
- **Definition of done:** LLM variation reachable and clearly provenance-flagged.

### P2-1 — Preserve confidence/cost through the synchronous metrics path
- **Problem:** `/metrics/score` path and response builders drop `confidence`/`cost_usd`/`version`.
- **Evidence:** `evaluation/application/handlers.py:82-96`; `api/metrics.py`.
- **Affected modules:** `evaluation/application/handlers.py`, `api/metrics.py`.
- **Scope:** stop dropping fields in handlers and response builders.
- **Tests:** schema/response tests for confidence/cost.
- **Definition of done:** HTTP responses carry confidence/cost when present.

### P2-2 — Wire red-team semantic evaluation into a metric the general engine understands
- **Problem:** semantic effectiveness is separate from the metric registry.
- **Evidence:** `redteam/engine/semantic_judge.py` vs `evaluation/metrics`.
- **Scope:** expose semantic effectiveness as a first-class metric for aggregation/reporting once wired (P0-2).
- **Definition of done:** semantic effectiveness visible in analytics.

### P3-1 — Fix Groundedness metric metadata
- **Problem:** declares `HEURISTIC`, actually embedding-backed.
- **Evidence:** `groundedness_metric.py:28`; `implementations/__init__.py:60`.
- **Definition of done:** declared evaluator type matches implementation.

### P3-2 — Live-LLM smoke verification harness
- **Problem:** no automated test exercises a real provider (none would be run in CI by default).
- **Scope:** an opt-in, credentials-gated smoke test (`pytest -m real_provider`) guarded by env keys.
- **Definition of done:** documented command that, with real keys, runs one real evaluation and one red-team round.

---

## 11. Verification Performed

| Check | Result |
|---|---|
| `git status` | clean except pre-existing unrelated `frontend/package-lock.json` (preserved, not modified) |
| `git branch --show-current` | `develop` |
| `git log --oneline -15` | recent security/infra fixes confirmed |
| pytest `backend/tests/redteam/` | **144 passed** |
| pytest `backend/tests/evaluation/` + `integration/test_evaluation_pipeline.py` + `integration/test_provider_registration.py` | **1303 passed** |
| pytest `redteam/test_safety_metrics.py` + `evaluation/reliability/test_golden_evaluation.py` | **36 passed** |
| Live external-provider call | **NOT RUN** — no real API credentials available in `.env` (placeholder stubs); documented as remaining runtime verification |

No production code, metrics, datasets, providers, APIs, schema, or Temporal workflows were modified. Scope rule (Phase 9) honored — only this audit document was produced.

---

## 12. Honest Bottom Line

- **Not "production-ready for credibility-sensitive use"** until ground-truth validation exists.
- **Architecture is real, not decorative:** the provider layer, Temporal orchestration, and real-LLM execution are genuinely implemented and well-tested against fake providers.
- **Largest credibility risk:** no ground truth → scores cannot be trusted/correctness cannot be shown; the red-team keyword-only evaluation with a hardcoded confidence compounds this.
- **Largest architectural risk:** the red-team subsystem's semantic judge and results persistence exist but are inert in production — a "built but not wired" pattern that leaves the headline safety metric weaker than it appears.
- **First thing to do next:** P0-1 (ground-truth dataset + validation pipeline) and P0-2 (wire the semantic judge into red-team), in that order — they directly address the two report claims (metric correctness, red-team keyword dependence) still true today.
