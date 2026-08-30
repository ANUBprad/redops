"""Enums for the ground-truth validation of safety metrics.

These enumerations define the vocabulary used to describe a *labeled*
validation example (ground truth) before a metric runs. They intentionally
reuse the existing RedOps safety taxonomy where it exists (see
``app.redteam.domain.enums``: ``SafetyVerdict``, ``SafetyDimension``,
``AttackSeverity``, ``AttackCategory``).

The ``GroundTruthSafetyLabel`` enum captures the *human ground-truth*
classification of an example as either safe or unsafe. This is deliberately a
simple binary so that metric predictions can be compared to reality; richer
category and severity analysis is carried separately via
``SafetyDimension``-compatible category strings and the existing severity
vocabulary.
"""

from __future__ import annotations

from enum import Enum, unique


@unique
class ValidationSplit(Enum):
    """Partition of a validation corpus used for honest evaluation.

    A held-out ``TEST`` split is mandatory before a metric can be claimed
    validated: the metric must never be tuned against the ``TEST`` split.
    """

    TRAIN = "train"
    DEV = "dev"
    TEST = "test"


@unique
class GroundTruthSafetyLabel(Enum):
    """The human ground-truth label for whether an example is safe.

    ``SAFE`` means the response is acceptable (no safety violation, or a
    correct refusal of an attack). ``UNSAFE`` means the response is harmful,
    leaks restricted data, complies with a malicious attack, or otherwise
    violates policy.
    """

    SAFE = "safe"
    UNSAFE = "unsafe"


@unique
class AnnotationConfidence(Enum):
    """Confidence of the human annotator that assigned the ground-truth label."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
