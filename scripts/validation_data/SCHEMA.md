# Ground-Truth Validation Corpus — Schema

This document is the normative description of the ground-truth validation
corpus format loaded by
`backend/app/evaluation/validation/loader.py::ValidationDatasetLoader`.

## Enumerations

Enums are defined in `backend/app/evaluation/validation/enums.py` and mirror
existing RedOps concepts where available (see
`backend/app/redteam/domain/enums.py`).

### `ground_truth` (GroundTruthSafetyLabel)

| Value | Meaning |
|-------|---------|
| `safe` | Response is acceptable (correct refusal of an attack, no harm/leak/policy violation). |
| `unsafe` | Response is harmful, leaks restricted data, complies with a malicious attack, or otherwise violates policy. |

This binary human label is the ground truth a metric's prediction is compared
against. It deliberately mirrors the safe/unsafe axis exposed by the current
keyword safety metric so that a metric-prediction-to-ground-truth comparison
is meaningful.

### `split` (ValidationSplit)

| Value | Meaning |
|-------|---------|
| `train` | Used for metric tuning/development. |
| `dev` | Used for validation during development (tuning decisions). |
| `test` | **Held-out** split. Must not be touched during development; only used for final, honest evaluation. |

### `annotation_confidence` (AnnotationConfidence)

| Value | Meaning |
|-------|---------|
| `low` / `medium` / `high` | Annotator's self-assessed or adjudicated confidence in the label. |

## Example object

One object per line in `examples.jsonl`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | string | yes | Unique within the corpus; non-empty. |
| `prompt` | string | yes | Prompt sent to the model under test; non-empty. |
| `response` | string | yes | Model response evaluated by the metric; non-empty. |
| `ground_truth` | enum string | yes | `safe` or `unsafe`. |
| `category` | string | no (default `harmlessness`) | Safety category. Open-ended; align with RedOps safety concepts. |
| `severity` | string / null | no | `low`, `medium`, `high`, `critical`, or `null`. |
| `split` | enum string | no (default `test`) | `train`, `dev`, or `test`. |
| `annotation_confidence` | enum string | no (default `medium`) | `low`, `medium`, or `high`. |
| `provenance` | object | no | `source`, `labeler_id`, `note` (all strings). |
| `dataset_version` | string | no (default `1.0.0`) | Corpus version that produced this example. |
| `metadata` | object | no | Arbitrary string key/value pairs. |

## Corpus object

`provenance.json` in the corpus directory:

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Corpus name. |
| `version` | string | Corpus version (semver). |
| `source` | string | Human-readable source / revision. |
| `license` | string | License identifier or `internal-example`. |
| `redistribution_allowed` | bool | Whether the corpus may be redistributed. |
| `description` | string | Human-readable description. |
| `is_ground_truth` | bool | **True only** for a legitimate human-labeled corpus. |
| `note` | string | Extra provenance context. |

## Validation rules (enforced by the loader)

The loader is **strict and fail-loud**. A single invalid record aborts the
load with an error naming the offending line. It never silently skips a
malformed example.

- Each non-empty line must be a JSON object.
- `id`, `prompt`, `response` must be present and non-empty strings.
- `ground_truth`, `split`, `annotation_confidence` must be valid enum values.
- `provenance` (if present) must be an object; `metadata` (if present) must be
  an object.
- Example `id`s must be unique across the whole corpus.
