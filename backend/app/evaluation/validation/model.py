"""Ground-truth validation domain objects.

A ``ValidationExample`` is a single labeled evaluation sample: the prompt and
response that were (or would be) evaluated, the human ground-truth safety
label, the safety category and severity, and the provenance metadata required
to reproduce and trust the label (source, labeler, annotator confidence, and
dataset split).

A ``ValidationDataset`` is an ordered, versioned collection of such examples
together with corpus-level provenance and licensing metadata.

Nothing in this module evaluates a metric or asserts that a metric is correct.
It only *represents* data that was labeled by (or accurately reproduced from)
a legitimate source. Examples whose labels were not produced by a legitimate
source must carry a provenance note stating that they are NOT ground truth.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeVar

from app.evaluation.validation.enums import (
    AnnotationConfidence,
    GroundTruthSafetyLabel,
    ValidationSplit,
)

T = TypeVar("T", bound=Enum)


@dataclass(frozen=True, slots=True)
class ExampleProvenance:
    """Provenance record for a single validation example.

    Attributes:
        source: Free-text source of the example (e.g. a public dataset name
            and revision, or ``synthetic-example`` for tooling fixtures).
        labeler_id: Identifier of the human (or process) that assigned the
            ground-truth label. Empty means the label was machine-produced.
        note: Additional provenance context, e.g. licensing or a statement
            that the example is a format demonstration and NOT ground truth.
    """

    source: str = ""
    labeler_id: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        """Serialize provenance to a plain dict."""
        return {
            "source": self.source,
            "labeler_id": self.labeler_id,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ExampleProvenance:
        """Create provenance from a validated dict of strings."""
        return cls(
            source=_opt_str(data.get("source")),
            labeler_id=_opt_str(data.get("labeler_id")),
            note=_opt_str(data.get("note")),
        )


@dataclass(frozen=True, slots=True)
class ValidationExample:
    """A single labeled example for ground-truth validation.

    Attributes:
        id: Unique identifier within the corpus.
        prompt: The prompt that was sent to the model under test.
        response: The model response that was (or is) evaluated by the metric.
        ground_truth: Human ground-truth safety classification.
        category: Safety category. Values align with RedOps safety concepts
            (e.g. harmlessness, data_confidentiality, policy_compliance) but
            are kept open-ended so a corpus can express its own category set.
        severity: Optional severity/risk level (e.g. low/medium/high/critical).
        split: Corpus partition this example belongs to.
        annotation_confidence: Confidence of the annotator.
        provenance: Provenance of the label and example.
        dataset_version: Version of the dataset that produced this example.
        metadata: Optional extra fields.
    """

    id: str
    prompt: str
    response: str
    ground_truth: GroundTruthSafetyLabel
    category: str = "harmlessness"
    severity: str | None = None
    split: ValidationSplit = ValidationSplit.TEST
    annotation_confidence: AnnotationConfidence = AnnotationConfidence.MEDIUM
    provenance: ExampleProvenance = field(default_factory=ExampleProvenance)
    dataset_version: str = "1.0.0"
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate example invariants."""
        if not self.id:
            msg = "Validation example id cannot be empty"
            raise ValueError(msg)
        if not self.prompt:
            msg = f"Validation example {self.id!r} prompt cannot be empty"
            raise ValueError(msg)
        if not self.response:
            msg = f"Validation example {self.id!r} response cannot be empty"
            raise ValueError(msg)

    @property
    def is_unsafe(self) -> bool:
        """True when the ground-truth label is UNSAFE."""
        return self.ground_truth is GroundTruthSafetyLabel.UNSAFE

    def to_dict(self) -> dict[str, object]:
        """Serialize the example to a plain JSON-serializable dict."""
        return {
            "id": self.id,
            "prompt": self.prompt,
            "response": self.response,
            "ground_truth": self.ground_truth.value,
            "category": self.category,
            "severity": self.severity,
            "split": self.split.value,
            "annotation_confidence": self.annotation_confidence.value,
            "provenance": self.provenance.to_dict(),
            "dataset_version": self.dataset_version,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ValidationExample:
        """Create a ``ValidationExample`` from a dict.

        Raises:
            ValueError: If required fields are missing or malformed. The
                loader layer wraps this with the line number, so callers can
                pinpoint the offending record.
        """
        example_id = _required_str(data, "id")
        prompt = _required_str(data, "prompt")
        response = _required_str(data, "response")
        ground_truth = _enum(
            GroundTruthSafetyLabel,
            _required_str(data, "ground_truth"),
            field="ground_truth",
        )
        split = _enum(ValidationSplit, _opt_str(data.get("split")) or "test", field="split")
        confidence = _enum(
            AnnotationConfidence,
            _opt_str(data.get("annotation_confidence")) or "medium",
            field="annotation_confidence",
        )
        raw_provenance = data.get("provenance")
        if raw_provenance is None:
            provenance = ExampleProvenance()
        elif isinstance(raw_provenance, Mapping):
            provenance = ExampleProvenance.from_dict(raw_provenance)
        else:
            msg = "example.provenance must be an object"
            raise ValueError(msg)

        raw_meta = data.get("metadata") or {}
        if not isinstance(raw_meta, Mapping):
            msg = "example.metadata must be an object"
            raise ValueError(msg)
        metadata = {str(key): str(value) for key, value in raw_meta.items()}

        return cls(
            id=example_id,
            prompt=prompt,
            response=response,
            ground_truth=ground_truth,
            category=_opt_str(data.get("category")) or "harmlessness",
            severity=_opt_severity(data.get("severity")),
            split=split,
            annotation_confidence=confidence,
            provenance=provenance,
            dataset_version=_opt_str(data.get("dataset_version")) or "1.0.0",
            metadata=metadata,
        )


@dataclass(frozen=True, slots=True)
class DatasetProvenance:
    """Corpus-level provenance and licensing metadata."""

    name: str = ""
    version: str = "1.0.0"
    source: str = ""
    license: str = ""
    redistribution_allowed: bool = False
    description: str = ""
    is_ground_truth: bool = False
    note: str = ""

    def to_dict(self) -> dict[str, object]:
        """Serialize corpus provenance to a plain dict."""
        return {
            "name": self.name,
            "version": self.version,
            "source": self.source,
            "license": self.license,
            "redistribution_allowed": self.redistribution_allowed,
            "description": self.description,
            "is_ground_truth": self.is_ground_truth,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> DatasetProvenance:
        """Create corpus provenance from a dict."""
        return cls(
            name=_opt_str(data.get("name")),
            version=_opt_str(data.get("version")) or "1.0.0",
            source=_opt_str(data.get("source")),
            license=_opt_str(data.get("license")),
            redistribution_allowed=bool(data.get("redistribution_allowed", False)),
            description=_opt_str(data.get("description")),
            is_ground_truth=bool(data.get("is_ground_truth", False)),
            note=_opt_str(data.get("note")),
        )


@dataclass(frozen=True, slots=True)
class ValidationDataset:
    """A versioned collection of labeled validation examples.

    Attributes:
        provenance: Corpus-level provenance/licensing metadata.
        examples: Ordered examples in file order.
    """

    provenance: DatasetProvenance
    examples: tuple[ValidationExample, ...]

    def __post_init__(self) -> None:
        """Validate the dataset and enforce unique example ids."""
        seen: set[str] = set()
        for example in self.examples:
            if example.id in seen:
                msg = f"Duplicate validation example id {example.id!r}"
                raise ValueError(msg)
            seen.add(example.id)

    @property
    def example_count(self) -> int:
        """Return the number of examples."""
        return len(self.examples)

    def examples_by_split(self, split: ValidationSplit) -> list[ValidationExample]:
        """Return examples belonging to the given split."""
        return [e for e in self.examples if e.split is split]

    def examples_by_category(self, category: str) -> list[ValidationExample]:
        """Return examples belonging to the given category."""
        return [e for e in self.examples if e.category == category]

    def examples_by_label(self, label: GroundTruthSafetyLabel) -> list[ValidationExample]:
        """Return examples with the given ground-truth label."""
        return [e for e in self.examples if e.ground_truth is label]

    def to_dict(self) -> dict[str, object]:
        """Serialize the dataset to a plain dict."""
        return {
            "provenance": self.provenance.to_dict(),
            "examples": [e.to_dict() for e in self.examples],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ValidationDataset:
        """Create a ``ValidationDataset`` from a dict.

        Raises:
            ValueError: If the structure is invalid.
        """
        raw_provenance = data.get("provenance") or {}
        if not isinstance(raw_provenance, Mapping):
            msg = "dataset.provenance must be an object"
            raise ValueError(msg)
        provenance = DatasetProvenance.from_dict(raw_provenance)
        raw_examples = data.get("examples")
        if isinstance(raw_examples, (str, bytes)) or not isinstance(raw_examples, Sequence):
            msg = "dataset.examples must be a list"
            raise ValueError(msg)
        examples = tuple(ValidationExample.from_dict(e) for e in raw_examples)
        return cls(provenance=provenance, examples=examples)


def _required_str(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        msg = f"example requires a non-empty '{key}' string"
        raise ValueError(msg)
    return value


def _opt_str(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _opt_severity(value: object) -> str | None:
    """Return None for missing/empty severity; otherwise the trimmed string."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _enum(enum_cls: type[T], raw: str, *, field: str) -> T:
    """Parse ``raw`` into an enum member of ``enum_cls``."""
    try:
        return enum_cls(raw)
    except ValueError as exc:
        allowed = ", ".join(member.value for member in enum_cls)
        msg = f"invalid {field} {raw!r} (allowed: {allowed})"
        raise ValueError(msg) from exc
