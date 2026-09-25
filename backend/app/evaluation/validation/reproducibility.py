"""Reproducibility support for ground-truth validation runs.

Validation runs record the metadata required to reproduce them exactly: the
dataset identifier/version, the dataset content hash, the metric name/version,
the scorer factory, metric parameters, the number of examples, and a
deterministic fingerprint binding dataset to metric configuration.

Reuses the repository's established fingerprinting mechanism
(``evaluation.reliability.fingerprint``) rather than inventing a parallel
hashing scheme.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from app.evaluation.reliability.fingerprint import (
    EvaluationFingerprint,
    compute_validation_fingerprint,
)
from app.evaluation.validation.model import ValidationDataset
from app.evaluation.validation.runner import MetricConfiguration, ValidationRunResult

__all__ = [
    "ValidationRunManifest",
    "build_run_manifest",
    "compute_dataset_hash",
]


def compute_dataset_hash(dataset: ValidationDataset) -> str:
    """Compute a deterministic SHA-256 hash of the corpus content.

    The hash covers every example in file order, so reordering or editing any
    example changes it. Uses the same canonical-JSON / SHA-256 approach as the
    repository's ``reliability.fingerprint`` helpers.

    Args:
        dataset: The validated corpus.

    Returns:
        A 64-character lowercase hex SHA-256 digest.
    """
    payload = [example.to_dict() for example in dataset.examples]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _example_fingerprints(dataset: ValidationDataset) -> tuple[str, ...]:
    """Return a stable per-example hash for each example in order."""
    return tuple(
        hashlib.sha256(
            json.dumps(
                example.to_dict(), sort_keys=True, separators=(",", ":"), default=str
            ).encode("utf-8")
        ).hexdigest()
        for example in dataset.examples
    )


@dataclass(frozen=True, slots=True)
class ValidationRunManifest:
    """Reproducibility manifest for a single validation run.

    Attributes:
        dataset_name: Corpus name.
        dataset_version: Corpus version.
        dataset_hash: Content hash of the corpus.
        metric: The metric configuration used.
        example_count: Number of examples evaluated.
        fingerprint: Deterministic fingerprint over dataset + metric.
        result: The validation run result (confidence counts + outcomes).
        extra: Optional extra reproducibility fields.
    """

    dataset_name: str = ""
    dataset_version: str = ""
    dataset_hash: str = ""
    metric: MetricConfiguration = field(default_factory=lambda: MetricConfiguration(name="unknown"))
    example_count: int = 0
    fingerprint: EvaluationFingerprint = field(
        default_factory=lambda: EvaluationFingerprint("", {})
    )
    result: ValidationRunResult = field(default_factory=ValidationRunResult)
    extra: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the manifest to a plain JSON-serializable dict."""
        return {
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "dataset_hash": self.dataset_hash,
            "metric": self.metric.as_dict(),
            "example_count": self.example_count,
            "fingerprint": self.fingerprint.fingerprint,
            "fingerprint_components": dict(self.fingerprint.components),
            "result": self.result.to_dict(),
            "extra": dict(self.extra),
        }


def build_run_manifest(
    dataset: ValidationDataset,
    result: ValidationRunResult,
    *,
    metric: MetricConfiguration | None = None,
    extra: dict[str, object] | None = None,
) -> ValidationRunManifest:
    """Assemble a reproducible manifest for a validation run.

    Args:
        dataset: The corpus that was evaluated.
        result: The run result produced from ``dataset``.
        metric: The metric configuration used (defaults to the result's).
        extra: Optional extra reproducibility fields (e.g. a build/tool version).

    Returns:
        A ``ValidationRunManifest`` with dataset hash, metric config, and a
        deterministic fingerprint binding the two.
    """
    effective_metric = metric or result.metric_configuration
    dataset_hash = compute_dataset_hash(dataset)
    fingerprint = compute_validation_fingerprint(
        dataset_hash=dataset_hash,
        metric_name=effective_metric.name,
        metric_version=effective_metric.version,
        scorer_factory=effective_metric.scorer_factory,
        parameters=effective_metric.parameters,
        example_fingerprints=_example_fingerprints(dataset),
    )
    return ValidationRunManifest(
        dataset_name=dataset.provenance.name,
        dataset_version=dataset.provenance.version,
        dataset_hash=dataset_hash,
        metric=effective_metric,
        example_count=result.example_count,
        fingerprint=fingerprint,
        result=result,
        extra=extra or {},
    )
