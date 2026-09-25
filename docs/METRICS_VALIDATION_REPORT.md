# RedOps Metrics — Ground-Truth Validation Report

**Date:** 2026-08-30
**Branch:** `develop`
**Status:** FOUNDATION COMPLETE — METRICS **NOT VALIDATED**

This report implements the reporting methodology required before any metric
correctness claim can be made. It follows the structure mandated by the
credibility-gap roadmap (P0-1): methodology, dataset information, actual
measured results, limitations, failure analysis, and conclusions.

---

## 1. Methodology

Metric validation measures an **existing RedOps metric's binary prediction**
against a **human ground-truth label** and records the result as confusion
counts (TP / TN / FP / FN). Precision, recall, F1, and accuracy are **derived**
from these counts; the runner stores only the raw counts and does **not**
hardcode any expected/target performance value.

The scoring path for the keyword safety metric is:

1. The example's `prompt` and `response` are wrapped in the same
   `AttackResult`/`AttackScenario` objects the red-team pipeline uses.
2. `redteam.metrics.safety.score_result` produces one `SafetyVerdict` per
   safety dimension.
3. `overall_verdict` aggregates to a single verdict.
4. Verdict `VIOLATED`/`LEAKED` map to a binary **UNSAFE** prediction;
   `SAFE`/`SUSPICIOUS` map to **SAFE** (a `SUSPICIOUS` uncertain verdict is
   scored conservatively as SAFE rather than as a violation).

Existing metric semantics are **unchanged**; this report only *measures* them.

The comparison machinery accepts any scorer implementing
`app.evaluation.validation.runner.MetricScorer` (`prompt, response -> bool`),
so a future semantic LLM judge can be validated with the identical comparator
without changing the runner.

## 2. Dataset Information

**The validation corpus is currently NOT populated with legitimate ground
truth.**

The corpus directory (`scripts/validation_data/examples/`) contains only a
**schema/format demonstration** corpus. Its provenance explicitly sets
`is_ground_truth: false` and each example's provenance note states it is
**NOT ground truth**. It exists solely to exercise the loader, quality checks,
runner, and tests.

| Field | Value |
|-------|-------|
| Corpus name | `redops-schema-example` |
| Corpus version | `0.1.0` |
| `is_ground_truth` | `false` |
| Status | **Unpopulated** (format demonstration only) |

## 3. Actual Measured Results

**No metric-accuracy results are reported, because there is no legitimate
ground-truth corpus to measure against.**

Specific metrics (e.g. keyword safety, and later the semantic judge) therefore
have **NO measured precision, recall, F1, or accuracy**. The numbers from the
external report (e.g. 79.17% / 73.08%) are **not reproduced and are not
claimed**.

The validation runner, loader, quality checks, and reproducibility manifest
are implemented and unit-tested (deterministic, offline), so the machinery is
ready to produce honest numbers *as soon as a legitimate corpus is added*.

## 4. Limitations

- **No legitimate labeled corpus exists in this environment.** The repository
  contains no human-labeled ground-truth safety dataset, and the `.env`
  contains no usable external API credentials, so none could be generated or
  fetched here.
- Metric accuracy cannot be stated nor inferred from the unit tests; passing
  tests demonstrate the *machinery* works, not that the metric is correct.
- The keyword safety metric itself is a heuristic with a known hardcoded
  `confidence=0.8` (see `redteam/metrics/safety.py:67`) and no ground-truth
  anchor; validating it (or replacing it) is a separate, later step.

## 5. Failure Analysis

Not applicable yet — there are no validation results to analyze. When a corpus
is populated, any disagreement between the metric prediction and ground truth
will appear as false positives/negatives in the confusion output, grouped by
category, making failure analysis straightforward. The runner is built to
surface exactly this.

## 6. Conclusions

**Explicitly: the RedOps safety metrics are NOT YET VALIDATED.**

- The ground-truth validation foundation (data model, strict loader, quality
  checks, runner, reproducibility, reporting) is implemented and tested.
- No metric is claimed accurate or production-ready for credibility-sensitive
  use until:
  1. a legitimate, license-cleared, human-labeled ground-truth corpus is
     populated (with provenance, annotation confidence, and a held-out `test`
     split);
  2. the runner is executed against that corpus;
  3. and the resulting confusion metrics are reported here with confidence
     intervals.

Until then, any number derived from this system must be labeled an
**unsupported measurement**.
