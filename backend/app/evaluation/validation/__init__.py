"""Ground-truth validation foundation.

Provides the typed data model, strict JSONL loader, deterministic quality
checks, validation runner, and reproducibility manifest used to measure the
correctness of RedOps safety metrics against human-labeled ground truth.

The purpose of this subpackage is to establish a *rigorous mechanism* through
which metric correctness can later be measured honestly. Nothing here asserts
that any metric is already accurate; results are structured so precision,
recall, F1, accuracy, and per-category analysis can be derived from the
recorded confusion counts.
"""

from app.evaluation.validation.enums import (
    AnnotationConfidence,
    GroundTruthSafetyLabel,
    ValidationSplit,
)
from app.evaluation.validation.loader import (
    ValidationDatasetLoader,
    ValidationDatasetLoadError,
    load_validation_items,
)
from app.evaluation.validation.model import (
    DatasetProvenance,
    ExampleProvenance,
    ValidationDataset,
    ValidationExample,
)
from app.evaluation.validation.quality import (
    DatasetStatistics,
    compute_statistics,
    validate_split_has_test,
)
from app.evaluation.validation.reproducibility import (
    ValidationRunManifest,
    build_run_manifest,
    compute_dataset_hash,
)
from app.evaluation.validation.runner import (
    DEFAULT_METRIC_CONFIGURATION,
    DEFAULT_SCORER,
    ConfusionCounts,
    ExampleOutcome,
    MetricConfiguration,
    MetricScorer,
    ValidationRunResult,
    keyword_safety_scorer,
    run_validation,
)

__all__ = [
    "DEFAULT_METRIC_CONFIGURATION",
    "DEFAULT_SCORER",
    "AnnotationConfidence",
    "ConfusionCounts",
    "DatasetProvenance",
    "DatasetStatistics",
    "ExampleOutcome",
    "ExampleProvenance",
    "GroundTruthSafetyLabel",
    "MetricConfiguration",
    "MetricScorer",
    "ValidationDataset",
    "ValidationDatasetLoadError",
    "ValidationDatasetLoader",
    "ValidationExample",
    "ValidationRunManifest",
    "ValidationRunResult",
    "ValidationSplit",
    "build_run_manifest",
    "compute_dataset_hash",
    "compute_statistics",
    "keyword_safety_scorer",
    "load_validation_items",
    "run_validation",
    "validate_split_has_test",
]
