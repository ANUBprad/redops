# P6-B: Red-Team Configuration Findings — Forensic Reassessment

**Date:** 2026-09-16
**Type:** Read-only forensic audit (no production changes, no test changes, no migration, no frontend changes, no `opencode.md` changes)
**Baseline:** `99737741b47c58beed058c6f5952d75a41e1c1aa` (`fix(redteam): propagate system prompt`) — `HEAD == origin/develop`, branch `develop`

---

## 1. Scope

Reassess the four P6-B findings that were **not** closed by P6-B1–B4 (commits `64bb038`, `750f4cb`, `ec698da`, `9973774`):

1. `attack_definition_ids` (accepted but not consumed)
2. `severities` (scenario severity always `"medium"`)
3. `max_scenarios` (count always 1)
4. `continue_on_violation` (never read)

Classification standard: **Genuine defect** = a field has a documented/established runtime contract and execution fails to honor it. A field with no established consumer or contract is not a defect; it is classified as unsupported/deferred, dead-unused, documentation inconsistency, or ambiguous. No semantics are invented for fields that execution does not consume.

The reassessed findings are **not** ranked against one another. P6-B1–B4 were *verified* only as regression evidence (their tests re-run), not re-audited.

---

## 2. Current baseline

- `HEAD` = `99737741b47c58beed058c6f5952d75a41e1c1aa`
- `origin/develop` = `99737741b47c58beed058c6f5952d75a41e1c1aa`
- Branch: `develop`
- Working tree: only pre-existing unrelated changes (`backend/app/agents/runtime/agent_loop.py`, `frontend/package-lock.json`, `opencode.md` modified; untracked `AGENTS.md` + prior audit reports). No new production/test/migration files from this audit.

---

## 3. Finding 1 — `attack_definition_ids` / `attack_definitions`

**Current behavior:** `CreateAttackRunRequest.attack_definition_ids: list[str]` (`schemas/redteam.py:114`) is forwarded to `CreateAttackRunCommand.attack_definition_ids` (`commands.py:74` via `api/redteam.py:353`), converted to `tuple[UUIDv7, ...]` and stored on the `AttackRun` aggregate (`entities.py:213,226,243-244`), and persisted to the `attack_runs.attack_definition_ids` JSON column (`models/attack_run.py:20`). The same data also enters the config blob via the `configuration.attack_definitions` key (`handlers.py:309-311` → `AttackConfiguration.attack_definitions` `value_objects.py:94`, persisted at `attack_run_repository.py:196`). The GET response returns the top-level IDs (`api/redteam.py:141`). The `AttackRunCreated` domain event carries `attack_count=len(attack_definition_ids)` (`entities.py:309`).

**Data lifecycle:** request → command → `AttackRun` aggregate → DB. Two redundant storage locations for the same concept: the `attack_definition_ids` column and the `configuration["attack_definitions"]` JSON key. Both hydrate back on read (`attack_run_repository.py:196,220`). Neither location is read by any execution path.

**Established contract:** A complete `AttackDefinition` resource exists and is served (CRUD endpoints `api/redteam.py`, `SqlAlchemyAttackDefinitionRepository`, domain entity `entities.py:31-130`, DB table `models/attack_definition.py` with `template`/`parameters` JSON columns). However, **no documentation or code establishes that run-scoped definition IDs drive scenario generation.** The API type is `list[str]` with no defined selection semantics.

**Runtime consumer:** none. Scenario generation is `campaign_engine._generate_scenario` → `_orchestrator.generate_scenarios(category, template={}, parameters={}, count=1)` (`campaign_engine.py:244-249`), which uses builtin category templates (`categories.py:93-129`) with `attack_definition_id` never set to a stored definition ID. No repository lookup of `AttackDefinition` by ID exists outside the definition CRUD handlers.

**Evidence:** `schemas/redteam.py:76,114`; `commands.py:74`; `api/redteam.py:141,353`; `entities.py:213,226,243-244,309`; `handlers.py:195-205,309-311`; `models/attack_run.py:20`; `models/attack_definition.py`; `campaign_engine.py:244-249`; `categories.py:93-129`; `orchestrator.py:35-36`; `attack_run_repository.py:196,220`. Test: `tests/redteam/test_domain_entities.py:116-120` (asserts entity round-trip only; no execution contract asserted).

**Classification:** **Unsupported/deferred** (was F in P6-B: metadata/future-facing). The audit stays a metadata/feature gap: faithfully accepted, persisted, and echoed, with a complete CRUD surface for the referenced resource, but no runtime contract that execution must honor. Not a genuine defect under the standard above.

**Priority reassessment:** unchanged (P3 — no functional impact today; no user-visible breakage).

**Recommended action:** none now. Optionally: (a) document that definition selection is future work pending a DefinitionBasedAttackEngine, or (b) remove the run-scoped field if the feature is abandoned. Do **not** wire selection until the selection semantics are defined.

---

## 4. Finding 2 — `severities` (scenario severity always `"medium"`)

**Current behavior:** `AttackConfiguration.severities: tuple[AttackSeverity, ...]` (`value_objects.py:96`) is hydrated from the free-form `configuration` dict (`handlers.py:313`) and persisted (`attack_run_repository.py:198,222`). It is **not** forwarded into `RedTeamWorkflowInput` at run start — the start endpoint forwards only `target_*`, `system_prompt`, `mutation_*`, `max_rounds`, `max_cost_usd`, `max_duration_seconds`, and `attack_categories` (`api/redteam.py:427-441`; `activities.py:120-139`). Scenario generation passes `parameters={}` (`campaign_engine.py:246-247`), so `categories.py:122` yields `AttackSeverity(parameters.get("severity", "medium"))` = `"medium"` on every scenario.

**Data lifecycle:** config dict (`dict[str, Any]`, no typed schema) → `AttackConfiguration.severities` → config JSON blob → hydrated on read. Never forwarded to workflow/activity/engine.

**Established contract:** none for *config-filtering semantics*. `configuration` is `dict[str, Any]` (`schemas/redteam.py:115`) — the key is accepted by free-form, not by a documented field contract. No test or doc defines that `severities` should filter/select scenario severity. (Severity as a *downstream attribute* is real: `scenario.severity` flows into `FindingPayload` and the semantic-judge/metrics metadata and campaign-report severity distribution — but always with the `"medium"` default.)

**Runtime consumer:** the scenario severity *attribute* is consumed downstream (`activities.py:270` finding payload, `attack_evaluator.py:147,188`, `campaign_report.py` severity distribution) but is always the default `"medium"`. The configuration `severities` tuple has no consumer.

**Evidence:** `value_objects.py:96`; `handlers.py:296-320` (esp. 313); `attack_run_repository.py:198,222`; `api/redteam.py:425-441`; `activities.py:120-139`; `campaign_engine.py:244-249`; `categories.py:122`; `schemas/redteam.py:115`; `attack_evaluator.py:62,147,188`; `activities.py:270`; `campaign_report.py:20,37,78,87,119,150,187-188,192,200,219,265-277`. No test references `configuration.severities` (verified: zero matches in `backend/tests`).

**Classification:** **Unsupported/deferred** (was D in P6-B: consumed with unintended hard-code `"medium"`). The severity *attribute* is consumed with a constant default; the config field has no established selection contract. Not a genuine defect under the standard above — a severity filter was never documented, so the engine's default is not a broken promise.

**Priority reassessment:** unchanged (P3).

**Recommended action:** none now. If severity selection is wanted, the feature gap is: (a) add `severities`/severity forwarding to `RedTeamWorkflowInput` + workflow→activity, (b) select scenario severity from it in scenario generation. Otherwise document that severity is informational only. The observable `"medium"` in all reports is a **documentation inconsistency** risk, flagged under Remaining Work.

---

## 5. Finding 3 — `max_scenarios` (count always 1)

**Current behavior:** `AttackConfiguration.max_scenarios: int = 0` (`value_objects.py:97`) is hydrated from the config dict (`handlers.py:314`), persisted (`attack_run_repository.py:199,223`). Scenario generation always requests `count=1` (`campaign_engine.py:248`). `max_scenarios` is not forwarded into `RedTeamWorkflowInput`, and there is no consumer anywhere in the runtime.

**Data lifecycle:** config dict → `AttackConfiguration.max_scenarios` → config JSON → hydrated on read. Never forwarded; never read at runtime.

**Established contract:** none. Free-form config key; no test, doc, or consumer references it (zero matches in `backend/tests`).

**Runtime consumer:** none. `count=1` is a hardcoded loop constant chosen for the round-based adaptive loop, not a violation of a documented `max_scenarios` contract.

**Evidence:** `value_objects.py:97`; `handlers.py:314`; `attack_run_repository.py:199,223`; `campaign_engine.py:246-249`; `activities.py:120-139`; no engine/workflow reference.

**Classification:** **Dead-unused** (was D in P6-B: "always 1"). The field is persisted-only with no runtime consumer and no contract. Not a genuine defect.

**Priority reassessment:** unchanged (P3).

**Recommended action:** remove the field from `AttackConfiguration` and the repo serializer/hydrator, or define its semantics (e.g., per-round scenario cap). Doing nothing is acceptable but leaves dead surface area in the persisted config contract.

---

## 6. Finding 4 — `continue_on_violation`

**Current behavior:** `AttackConfiguration.continue_on_violation: bool = True` (`value_objects.py:102`) is hydrated from the config dict (`handlers.py:318`), persisted (`attack_run_repository.py:204,228`). It is never forwarded into `RedTeamWorkflowInput` and never read by the engine. Early-stop behavior exists but is driven by `budget.effectiveness_threshold` and consecutive-error counting (`campaign_engine.py:268-288`, `_should_stop_early`), which are unrelated to violation-continuation semantics.

**Data lifecycle:** config dict → `AttackConfiguration.continue_on_violation` → config JSON → hydrated on read. Never forwarded; never read at runtime.

**Established contract:** none. Free-form config key; no test or doc defines continuation-on-violation semantics (zero matches in `backend/tests`).

**Runtime consumer:** none.

**Evidence:** `value_objects.py:102`; `handlers.py:318`; `attack_run_repository.py:204,228`; `campaign_engine.py:126-157,268-288`; `activities.py:120-139`; no engine/workflow/evaluator reference.

**Classification:** **Dead-unused** (was D in P6-B: "always True"). Persisted-only field with no consumer and no contract. Not a genuine defect.

**Priority reassessment:** unchanged (P3).

**Recommended action:** remove the field from `AttackConfiguration` + repo serializer/hydrator, or define semantics (e.g., stop campaign on first severe violation) and wire it through workflow → engine. Doing nothing accepts the dead field.

---

## 7. P6-B closure matrix

| P6-B finding | P6-B intent | Status | Reassessed classification |
|---|---|---|---|
| temperature/max_tokens hard-coded (P1/D) | P6-B1 fix (`64bb038`) | **Closed** | verified: `campaign_engine.py:215-216`, `api/redteam.py:431-432`, `workflow.py:70-71` |
| mutation provider/model/strategy dropped (P2/B+E) | P6-B2 fix (`750f4cb`) | **Closed** | verified: `handlers.py:304-306`, `api/redteam.py:434-436`, `workflow.py:73-75` |
| budget fields unconfigurable (P2/E+D) | P6-B3 fix (`ec698da`) | **Closed** | verified: `handlers.py:315-317`, `api/redteam.py:437-439`, `activities.py:395-398` |
| system_prompt not forwarded (P2/D) | P6-B4 fix (`9973774`) | **Closed** | verified: `handlers.py:308`, `api/redteam.py:433`, `workflow.py:72`, `campaign_engine.py:173-174` |
| mutations dropped at handler (P2/B+E) | P6-B2 fix (`750f4cb`) | **Closed** | verified: repo hydrator parses mutations; handler path now propagates mutation fields (covered by `test_mutation_configuration_fidelity.py`) |
| `attack_definition_ids` not consumed (P3/F) | none (deferred) | **Open (deferred)** | **Unsupported/deferred** |
| `severities` always medium (P3/D) | none (optional) | **Open (deferred)** | **Unsupported/deferred** (plus documentation inconsistency flagged) |
| `max_scenarios` always 1 (P3/D) | none (optional) | **Open (not planned)** | **Dead-unused** |
| `continue_on_violation` always True (P3/D) | none (optional) | **Open (not planned)** | **Dead-unused** |

No finding is reassessed as a **genuine defect**: none of the four has a documented/established runtime contract that execution fails to honor. None rose in priority.

---

## 8. P6-A/B regression evidence

Baseline suite runs at `99737741b47c58beed058c6f5952d75a41e1c1aa`:

- **Full red-team suite** `pytest tests/redteam -q`: **243 passed** (16.92s) — matches the P6-B4 gate (243).
- **Targeted fidelity + lifecycle regression** (10 files: `test_campaign_cancellation.py`, `test_redteam_lifecycle.py`, `test_target_generation_parameters.py`, `test_system_prompt_configuration_fidelity.py`, `test_mutation_configuration_fidelity.py`, `test_budget_configuration_fidelity.py`, `test_engine.py`, `test_handlers_lifecycle.py`, `test_domain_entities.py`, `test_campaign_engine.py`): **153 passed** (17.59s).

These confirm the P6-B1–B4 fixes are intact at HEAD (provider-boundary `ChatOptions`, mutation/config propagation through Temporal, budget enforcement, system-prompt propagation) and that no reassessment-related change broke behavior. `test_domain_entities.py:116-120` remains the only test touching `attack_definition_ids`; none of the four open findings has a test (no contract).

Full-suite count from the P6-B4 gate (context only): evaluation 1399, full backend 2796. Not re-run in this audit (targeted evidence sufficient).

---

## 9. Remaining work

### Confirmed engineering defects
- **None** newly confirmed by this reassessment. P6-B1–B4 remain the complete set of contract-violating defects previously found and are closed.

### Product/design decisions
- Whether run-scoped `attack_definition_ids` should drive scenario generation (requires a DefinitionBasedAttackEngine + defined selection semantics).
- Whether `severities` should filter/weight scenario selection at all.

### Unsupported/deferred
- `attack_definition_ids` / `AttackConfiguration.attack_definitions`: full CRUD + persistence exist; execution selection deferred.
- `severities` → scenario severity selection: needs forwarding through `RedTeamWorkflowInput` (workflow + activity) and scenario-generation wiring if productized.

### Dead-unused (candidates for removal)
- `max_scenarios` (`value_objects.py:97`, `handlers.py:314`, `attack_run_repository.py:199,223`).
- `continue_on_violation` (`value_objects.py:102`, `handlers.py:318`, `attack_run_repository.py:204,228`).
- Remove from `AttackConfiguration` + repo serializer/hydrator, or define semantics. No test depends on either (verified).

### Documentation issues
- `AttackRunResponse.configuration` is returned empty (`api/redteam.py:142`, hardcoded `{}`) while a rich config dict is persisted — response schema advertises `configuration: dict[str, Any]` but never populates it. Clients cannot read back what was configured.
- Reports surface `severity: "medium"` on every finding regardless of config (`categories.py:122`); documents alone should say severity is informational.
- The persisted config contract (keys accepted by `AttackConfiguration`) is undocumented relative to the free-form `dict[str, Any]` API surface (`schemas/redteam.py:115`).

---

## 10. Limitations

- Static analysis + targeted test execution only. No live provider calls, no DB writes, no workflow-spawned runs.
- "No established contract" is judged from repo code, tests, and docs at head; an external product/API spec could establish a contract this audit cannot see — that would move a finding toward Genuine defect.
- Working tree contains unrelated pre-existing modifications (`agent_loop.py`, `frontend/package-lock.json`, `opencode.md`); their content was untouched and they are excluded from the audit commit.
- No changes were made in this audit beyond creating this report.