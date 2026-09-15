# P4-A Audit: Dataset Identity & Execution Semantics

**Status:** No code change required. Audit only.
**Date:** 2026-09-15

## Question

Is `dataset_id` genuinely required for execution correctness, provenance,
auditability, analytics, API behavior, authorization, dataset versioning,
or reproducibility — given the P3-4 snapshot model?

## Method

Traced both live execution paths (normal create → workflow → activity →
provider, and retry source → new run → workflow) plus the evaluation
definition resource, analytics queries, and the API/router wiring.
Identifies the legacy in-memory orchestrator as a distinct, dead-for-API
path.

## Findings (numbered per the P4-A brief)

1. **Where `dataset_id` originates.** It exists ONLY on the evaluation
   *definition* CRUD resource: `CreateEvaluationRequest.dataset_id` /
   `UpdateEvaluationRequest.dataset_id` (`backend/app/schemas/evaluation.py`),
   persisted on the `evaluations.dataset_id` column
   (`backend/app/infrastructure/database/models/evaluation.py:25`),
   exposed in `EvaluationResponse`
   (`backend/app/api/evaluation.py:61`). The run-creation request
   (`CreateEvaluationRunRequest`, `backend/app/schemas/evaluation_run.py`) has
   **no** `dataset_id` field and the run endpoint never loads the definition,
   so a run has no dataset_id at creation.

2. **Persisted anywhere?** For runs: no. The run's serialized
   `config.dataset` is always `null` on the live path
   (`_serialize_config`, `evaluation_run_repository.py:400-404`); the field
   is only populated by the legacy factory path
   (`EvaluationConfigurationFactory.create(... dataset=...)`), which the
   API does not use. `dataset_id` IS persisted on the *definition*
   (`evaluations` table).

3. **Passed into the workflow?** No. `EvaluationRunWorkflowInput`
   (`evaluation/temporal/workflow.py:59-66`) carries run_id, total_items,
   provider/model, metrics, dataset_items, prompt_template, system_prompt.
   No dataset_id. Execution indexes `input.dataset_items`
   (`workflow.py:269-271`).

4. **Is DatasetStore involved?** Only in the legacy in-memory orchestrator
   (`EvaluationPlanner` → `InMemoryDatasetStore`,
   `orchestration/planner.py:124`, `orchestration/orchestrator.py`), which
   is dead for the API path (no API caller constructs it; `test_real_item_execution.py`
   exercises that legacy path only). No `/datasets` router exists
   (`api/router.py:26-44`; grep for `datasets`/`dataset_router` finds none).

5. **Are dataset_items authoritative execution inputs?** Yes (P3-4). Item
   content comes strictly from the persisted snapshot in `config.dataset_items`
   → workflow input → `activities.py:455-460` `DatasetItem` construction.

6. **Is dataset_id only metadata?** Yes. It describes what dataset a
   *definition* is notionally about. Nothing in the live execution chain
   reads it.

7. **Versions/revisions?** `DatasetReference.version` and
   `EvaluationDataset.version` exist but are never populated or consumed by
   live code. `docs/API_SPEC.md` projects a `/datasets/{id}/versions` CRUD
   that is not implemented. Versioning is a spec concept, not executed
   behavior.

8. **Authorization?** No dataset-level access control exists; project/user
   scoping is via tenant/project/created_by. Nothing authorizes by
   dataset_id.

9. **API responses expose dataset identity?** `EvaluationResponse.dataset_id`
   (definition). Run responses (`RunResponse`) expose `evaluation_id` but no
   dataset identity; `evaluation_id` → definition → dataset_id is joinable
   for the current definition.

10. **Analytics requires it?** No. `/analytics/trends` accepts no
    `dataset_id` param (`analytics/api/router.py:315-345`); the
    `GetHistoricalTrendsQuery.dataset_id` field is dead/unwired. Trends filter
    by provider/model/date across MetricResults, which carry no dataset_id.

11. **Retry faithful without dataset_id?** Yes. The P3-4 snapshot of
    `dataset_items` + `prompt_template` reproduces exact evaluation content;
    `dataset_id` adds a label, not content.

12. **Real correctness defect?** None in execution. Every executed artifact
    the run needs is snapshotted on the run. `dataset_id` is useful *future*
    metadata for a datasets resource that does not exist yet.

## Comparison with the P3-4 snapshot model

P3-4 made the run self-contained (content + template persisted). Under that
model the dataset the run *should have used* — the definition's `dataset_id`
— is a secondary label whose source resource is unimplemented. Propagating
`dataset_id` now would persist metadata with no consuming code path.

## Decision

**No code change.** Adding `dataset_id` persistence to runs would be
inventing persistence nothing consumes (YAGNI; opencode.md §3.6). It is not
required for execution, retry fidelity, authorization, or analytics.

When a real `/datasets` resource with versions is implemented, revisit:
then deciding whether a run should snapshot the referenced `dataset_id`
(identity) alongside its `dataset_items` (content) becomes a real
design question.

## Evidence map

- Run request schema: `backend/app/schemas/evaluation_run.py:25-57`
- Workflow input: `backend/app/evaluation/temporal/workflow.py:59-66`
- Item resolution: `backend/app/evaluation/temporal/workflow.py:269-271`
- Item construction: `backend/app/evaluation/temporal/activities.py:455-460`
- Definition dataset_id: `backend/app/api/evaluation.py:56-74,103-129`
- Legacy planner/DatasetStore: `backend/app/evaluation/orchestration/planner.py:124`
- No datasets router: `backend/app/api/router.py:26-44`
- Analytics (dead field): `backend/app/analytics/application/commands.py:24`
- Serialized run config dataset: `backend/app/infrastructure/database/repositories/evaluation_run_repository.py:400-404`