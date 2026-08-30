"""Validation runner foundation.

Applies an existing RedOps safety metric to each example in a ground-truth
corpus and compares the metric's binary prediction against the human
ground-truth label.

Purpose
-------
The purpose of this phase is the *foundation* for measuring metric
correctness - NOT to claim the metric is accurate. The runner deliberately:

- computes a confusion-matrix-ready outcome for every example
  (true/false positive/negative), so precision/recall/F1/accuracy can be
  computed later;
- records every per-example prediction, verdict, and the metric configuration
  used, so no number can be confused between "metric changed" and "dataset
  changed";
- never hardcodes or implies an expected accuracy/precision/recall target.

Design
------
The metric is injected as a ``MetricScorer`` callable defaulting to
``app.redteam.metrics.safety.score_result`` followed by ``overall_verdict``.
Any future evaluator (e.g. a semantic LLM judge) can be wrapped in the same
``MetricScorer`` protocol and validated with the identical comparison
machinery - no changes to the runner internals.

Current RedOps metric semantics are preserved unchanged (nothing here modifies
``score_result``). The mapping below is documented in PHASE 2 of the
validation task: ground-truth SAFE/UNSAFE is the *human* label; the metric's
``SafetyVerdict`` is the *prediction*. Verdicts VIOLATED/LEAKED map to an
UNSAFE prediction; SAFE/SUSPICIOUS map to a SAFE prediction so that a
SUSPICIOUS (uncertain) verdict is scored as SAFE rather than counted as a
violation (conservative direction consistent with the metric's own semantics).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.evaluation.validation.enums import GroundTruthSafetyLabel
from app.evaluation.validation.model import ValidationDataset, ValidationExample
from app.evaluation.validation.quality import compute_statistics
from app.redteam.domain.enums import SafetyVerdict
from app.redteam.domain.value_objects import AttackResult, AttackScenario
from app.redteam.metrics.safety import overall_verdict, score_result


class MetricScorer(Protocol):
    """Protocol for a metric that maps a prompt/response to a binary prediction.

    A scorer receives the example text and returns ``True`` when it predicts
    UNSAFE, ``False`` when it predicts SAFE. The runner compares this against
    the example's ground-truth label.
    """

    def __call__(self, *, prompt: str, response: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class MetricConfiguration:
    """Identifies the exact metric configuration used in a validation run.

    This metadata makes each validation run reproducible and makes it
    impossible to confuse "the metric implementation changed" with "the
    dataset changed".
    """

    name: str
    version: str = "unknown"
    scorer_factory: str = ""
    parameters: dict[str, object] = field(default_factory=dict)
    description: str = ""

    def as_dict(self) -> dict[str, object]:
        """Serialize the configuration to a plain dict."""
        return {
            "name": self.name,
            "version": self.version,
            "scorer_factory": self.scorer_factory,
            "parameters": dict(self.parameters),
            "description": self.description,
        }


def keyword_safety_scorer(*, prompt: str, response: str) -> bool:
    """Predict UNSAFE using the existing RedOps keyword safety metric.

    Builds an ``AttackResult`` in the same way the red-team pipeline does and
    scores it with ``score_result`` + ``overall_verdict``. Returns ``True``
    when the overall verdict is VIOLATED or LEAKED.

    The keyword safety metric's hardcoded ``confidence=0.8`` is intentionally
    not used here; this scorer only consumes the verdict.
    """
    scenario = AttackScenario(prompt=prompt)
    result = AttackResult(scenario=scenario, response=response)
    verdict = overall_verdict(score_result(result))
    return verdict in (SafetyVerdict.VIOLATED, SafetyVerdict.LEAKED)


DEFAULT_METRIC_CONFIGURATION = MetricConfiguration(
    name="keyword_safety",
    version="0.1.0",
    scorer_factory="app.evaluation.validation.runner.keyword_safety_scorer",
    description=(
        "RedOps keyword-based safety metric (redteam.metrics.safety). "
        "Binary prediction: overall verdict VIOLATED/LEAKED => UNSAFE."
    ),
)

DEFAULT_SCORER: Callable[..., bool] = keyword_safety_scorer


@dataclass(frozen=True, slots=True)
class ExampleOutcome:
    """The comparator result for a single example."""

    example_id: str
    ground_truth: GroundTruthSafetyLabel
    predicted_unsafe: bool
    category: str
    split: str
    overall_verdict: str
    is_true_positive: bool = False
    is_true_negative: bool = False
    is_false_positive: bool = False
    is_false_negative: bool = False

    @property
    def predicted_label(self) -> GroundTruthSafetyLabel:
        """Derive the predicted binary label from the boolean prediction."""
        return (
            GroundTruthSafetyLabel.UNSAFE if self.predicted_unsafe else GroundTruthSafetyLabel.SAFE
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize the outcome to a plain JSON-serializable dict."""
        return {
            "example_id": self.example_id,
            "ground_truth": self.ground_truth.value,
            "predicted_label": self.predicted_label.value,
            "predicted_unsafe": self.predicted_unsafe,
            "category": self.category,
            "split": self.split,
            "overall_verdict": self.overall_verdict,
            "is_true_positive": self.is_true_positive,
            "is_true_negative": self.is_true_negative,
            "is_false_positive": self.is_false_positive,
            "is_false_negative": self.is_false_negative,
        }


@dataclass(frozen=True, slots=True)
class ConfusionCounts:
    """Aggregate confusion-matrix counts for a validation run.

    These raw counts support later derivation of precision, recall, F1,
    accuracy, and per-category breakdowns. No derived rate is stored here so
    the runner itself never claims a performance number.
    """

    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def total(self) -> int:
        """Total number of examples in this aggregation bucket."""
        return (
            self.true_positives + self.true_negatives + self.false_positives + self.false_negatives
        )

    def as_dict(self) -> dict[str, int]:
        """Serialize the counts to a plain dict."""
        return {
            "true_positives": self.true_positives,
            "true_negatives": self.true_negatives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
        }


@dataclass(frozen=True, slots=True)
class ValidationRunResult:
    """The full result of a validation run.

    Contains both the aggregate confusion counts and the per-example outcomes,
    plus the dataset and metric metadata needed to reproduce the run. This is
    the substrate on which future precision/recall/F1/accuracy reporting will
    be built; it carries no hardcoded performance expectation.
    """

    dataset_provenance: dict[str, object] = field(default_factory=dict)
    metric_configuration: MetricConfiguration = DEFAULT_METRIC_CONFIGURATION
    example_count: int = 0
    outcomes: tuple[ExampleOutcome, ...] = field(default_factory=tuple)
    overall: ConfusionCounts = field(default_factory=ConfusionCounts)
    category_counts: dict[str, ConfusionCounts] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Serialize the result to a plain JSON-serializable dict."""
        return {
            "dataset_provenance": dict(self.dataset_provenance),
            "metric_configuration": self.metric_configuration.as_dict(),
            "example_count": self.example_count,
            "outcomes": [o.as_dict() for o in self.outcomes],
            "overall": self.overall.as_dict(),
            "category_counts": {
                category: counts.as_dict() for category, counts in self.category_counts.items()
            },
        }


def run_validation(
    dataset: ValidationDataset,
    *,
    scorer: Callable[..., bool] | None = None,
    metric_configuration: MetricConfiguration | None = None,
    splits: Sequence[str] | None = None,
) -> ValidationRunResult:
    """Run a metric scorer against a ground-truth corpus.

    The default scorer is the existing RedOps keyword safety metric. Any
    scorer implementing the ``MetricScorer`` protocol can be substituted, but
    the stated metric configuration must match so results are reproducible.

    Args:
        dataset: The validated ground-truth corpus.
        scorer: A ``(prompt, response) -> bool`` predictor. Defaults to the
            keyword safety metric.
        metric_configuration: Metadata describing the scorer/configuration
            used. Must be supplied when a non-default scorer is passed.
        splits: Optional subset of split names to evaluate (e.g. ``["test"]``).

    Returns:
        A ``ValidationRunResult`` with per-example outcomes and aggregate
        confusion counts.
    """
    effective_scorer = scorer or DEFAULT_SCORER
    effective_config = metric_configuration or DEFAULT_METRIC_CONFIGURATION

    outcomes: list[ExampleOutcome] = []
    for example in dataset.examples:
        if splits is not None and example.split.value not in splits:
            continue
        outcome = _evaluate_example(example, effective_scorer)
        outcomes.append(outcome)

    overall = _aggregate(outcomes)
    category_counts = _aggregate_by_category(outcomes)

    stats = compute_statistics(dataset)
    provenance = {
        "name": dataset.provenance.name,
        "version": dataset.provenance.version,
        "source": dataset.provenance.source,
        "is_ground_truth": dataset.provenance.is_ground_truth,
        "notes": dataset.provenance.note,
        "example_count": stats.total_examples,
    }

    return ValidationRunResult(
        dataset_provenance=provenance,
        metric_configuration=effective_config,
        example_count=len(outcomes),
        outcomes=tuple(outcomes),
        overall=overall,
        category_counts=category_counts,
    )


def _evaluate_example(example: ValidationExample, scorer: Callable[..., bool]) -> ExampleOutcome:
    """Compute the comparator outcome for a single example."""
    predicted_unsafe = bool(scorer(prompt=example.prompt, response=example.response))

    is_unsafe_ground_truth = example.ground_truth is GroundTruthSafetyLabel.UNSAFE
    is_true_positive = predicted_unsafe and is_unsafe_ground_truth
    is_true_negative = (not predicted_unsafe) and (not is_unsafe_ground_truth)
    is_false_positive = predicted_unsafe and (not is_unsafe_ground_truth)
    is_false_negative = (not predicted_unsafe) and is_unsafe_ground_truth

    return ExampleOutcome(
        example_id=example.id,
        ground_truth=example.ground_truth,
        predicted_unsafe=predicted_unsafe,
        category=example.category,
        split=example.split.value,
        overall_verdict=_example_overall_verdict(example),
        is_true_positive=is_true_positive,
        is_true_negative=is_true_negative,
        is_false_positive=is_false_positive,
        is_false_negative=is_false_negative,
    )


def _example_overall_verdict(example: ValidationExample) -> str:
    """Return the metric's overall verdict string for the example (informational)."""
    scenario = AttackScenario(prompt=example.prompt)
    result = AttackResult(scenario=scenario, response=example.response)
    return overall_verdict(score_result(result)).value


def _aggregate(outcomes: Sequence[ExampleOutcome]) -> ConfusionCounts:
    """Aggregate confusion counts across outcomes."""
    return ConfusionCounts(
        true_positives=sum(1 for o in outcomes if o.is_true_positive),
        true_negatives=sum(1 for o in outcomes if o.is_true_negative),
        false_positives=sum(1 for o in outcomes if o.is_false_positive),
        false_negatives=sum(1 for o in outcomes if o.is_false_negative),
    )


def _aggregate_by_category(
    outcomes: Sequence[ExampleOutcome],
) -> dict[str, ConfusionCounts]:
    """Aggregate confusion counts grouped by category."""
    grouped: dict[str, list[ExampleOutcome]] = {}
    for outcome in outcomes:
        grouped.setdefault(outcome.category, []).append(outcome)
    return {category: _aggregate(items) for category, items in grouped.items()}
