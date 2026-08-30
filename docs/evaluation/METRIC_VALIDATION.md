# Metric Validation — Design Decisions

Context for the ground-truth validation foundation (P0-1). Documented decisions
make the reasons behind the design explicit so future contributors can
challenge them with full information.

## Why a version-controlled static JSONL corpus (not a database table)

The first iteration of ground-truth validation uses **versioned, static JSONL
files** rather than a new database table. Rationale:

1. **Validation corpora are versioned artifacts, not runtime records.** They
   are scientific assets that must be pinned, reviewed, and diffed in git. A
   static, human-readable corpus makes provenance review and reproducibility
   straightforward.
2. **No runtime consumer requires a DB representation today.** Nothing in the
   API, Temporal workflows, or UI reads validation corpora. Adding a table now
   would be premature and would create a parallel persistence layer
   contradicting the repo's reuse rule.
3. **Avoids evaluator leakage via the DB.** A git-reviewed static corpus makes
   the held-out `test` split explicit and auditable; it cannot be silently
   mutated by a running service.

If a future feature needs validation corpora served to the platform at runtime
(e.g. an evaluation job that pulls labeled items), a table + repository can be
added then, reusing the existing SQLAlchemy conventions. The domain model here
(`ValidationDataset`/`ValidationExample`) is designed to serialize cleanly, so
that migration is low-cost.

## Taxonomy reuse

Rather than inventing a parallel safety taxonomy, the validation layer reuses
existing RedOps concepts:

- `GroundTruthSafetyLabel { SAFE, UNSAFE }` is the **human** label. It is
  intentionally binary to keep a metric-prediction-to-ground-truth comparison
  well-defined and compatible with the current safe/unsafe axis.
- `ValidationSplit { train, dev, test }` and
  `AnnotationConfidence { low, medium, high }` are validation-specific enums
  with no existing RedOps equivalent.
- Safety **categories** are open-ended strings aligned with RedOps' safety
  vocabulary (e.g. `harmlessness`, `data_confidentiality`,
  `tool_governance`), so a corpus can express its own categories without being
  forced into `SafetyDimension`'s fixed set.
- `severity` reuses the existing `AttackSeverity` vocabulary
  (`low`/`medium`/`high`/`critical`) as strings.

### Ground truth → metric verdict mapping

The existing keyword metric produces a `SafetyVerdict` per dimension, then an
`overall_verdict`. The mapping to a binary prediction is:

| Metric overall verdict | Validation prediction |
|------------------------|-----------------------|
| `SAFE`, `SUSPICIOUS`   | `safe`                |
| `VIOLATED`, `LEAKED`   | `unsafe`              |
| `ERROR`                | depends (see below)   |

A `SUSPICIOUS` verdict maps to **safe** (conservative): an uncertain keyword
verdict is not counted as a violation. This preserves the metric's own
semantics; the validation layer does **not** change `score_result`.

No existing metric semantics were modified by this work.

## Binary safe/unsafe is sufficient for the first metric

For the first validation target (keyword safety), a binary safe/unsafe ground
truth is sufficient and is the only comparison the metric's verdict supports
directly. Category-level analysis is preserved by the per-example `category`
field and the runner's per-category confusion aggregation, so the foundation
does not preclude finer-grained analysis later.

## Reproducibility

Validation runs record a deterministic fingerprint binding the dataset content
hash to the metric name/version/scorer/parameters, reusing the repository's
established fingerprint mechanism (`evaluation.reliability.fingerprint`).
This prevents conflating "metric changed" with "dataset changed".
