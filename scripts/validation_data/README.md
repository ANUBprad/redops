# Ground-Truth Validation Data

This directory holds **ground-truth validation corpora** for measuring the
correctness of RedOps safety metrics.

## IMPORTANT

The current corpus under `examples/` is a **schema/format demonstration ONLY**.

- Its labels were written by an engineer to exercise the loader, quality
  checks, runner, and tests.
- It is **NOT a legitimate ground-truth corpus**.
- **It must never be used to support any claim about metric accuracy.**
- The provenance files explicitly mark it `"is_ground_truth": false`, and
  each example carries a `provenance.note` stating it is NOT ground truth.

Until a legitimate, license-cleared, human-labeled source is available, the
validation corpus is considered **unpopulated** for the purpose of metric
validation. See `docs/METRICS_VALIDATION_REPORT.md`.

## Directory layout

Each corpus is a directory containing:

```
<corpus>/
    examples.jsonl     # one labeled example per JSON line
    provenance.json    # corpus-level provenance + licensing metadata
```

### `examples.jsonl`

One JSON object per line. Required fields per example:

| Field                  | Type     | Notes                                                    |
|------------------------|----------|----------------------------------------------------------|
| `id`                   | string   | Unique within the corpus.                                |
| `prompt`               | string   | Prompt sent to the model under test.                     |
| `response`             | string   | Model response evaluated by the metric.                  |
| `ground_truth`         | string   | `safe` or `unsafe`.                                      |
| `category`             | string   | Safety category (e.g. `harmlessness`, `data_confidentiality`). |
| `severity`             | string?  | `low`, `medium`, `high`, `critical`, or `null`.         |
| `split`                | string   | `train`, `dev`, or `test`.                               |
| `annotation_confidence`| string   | `low`, `medium`, or `high`.                              |
| `provenance`           | object   | `source`, `labeler_id`, `note`.                          |
| `dataset_version`      | string   | Version of the corpus that produced this example.        |
| `metadata`             | object   | Optional extra key/value metadata.                       |

The loader rejects malformed records, invalid labels/confidence/split, and
duplicate ids **loudly** (never silently skipping them).

### `provenance.json`

Corpus-level metadata: `name`, `version`, `source`, `license`,
`redistribution_allowed`, `description`, `is_ground_truth`, `note`.

## Provenance & licensing rules

- **Never copy license-restricted content** into this repository. If a public
  dataset cannot be redistributed, do not add its rows here.
- Instead, implement an ingestion/conversion mechanism that reproduces the
  local corpus from a legally usable source, and document the source + license
  in `provenance.json`.
- Every corpus must record its source, license, redistribution terms, and
  whether it is genuine ground truth.
- A corpus is ground truth only when `is_ground_truth: true` and every example
  was labeled by (or accurately reproduced from) a legitimate, documented
  source.

## Split & evaluator-leakage rules

- Keep a held-out `test` split. Never tune or inspect the metric against the
  `test` split during development.
- Validation examples must not appear in prompt templates, system prompts, or
  any code path used at evaluation time.
- Record the dataset version + content hash with every validation run so
  "dataset changed" and "metric changed" are never confused.
