"""Typed loader for the ground-truth validation corpus.

The validation corpus lives in a directory following this layout::

    <dataset_dir>/
        examples.jsonl        # one labeled example per line
        provenance.json       # corpus-level provenance + licensing metadata

``examples.jsonl`` is the strict source of ground-truth examples; every
non-empty line must parse as a JSON object and every required field must be
present and well-typed. ``provenance.json`` is an optional sidecar carrying
corpus-level metadata (name, version, source, license, ``is_ground_truth``).

The loader is strict and fail-loud: a single malformed record aborts the whole
load with a message naming the offending line. It never silently skips a
malformed example, because silently weakening a validation corpus would
produce scientifically meaningless results.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Sequence

from app.evaluation.validation.model import DatasetProvenance, ValidationDataset

__all__ = [
    "ValidationDatasetLoadError",
    "ValidationDatasetLoader",
    "load_validation_items",
]


class ValidationDatasetLoadError(ValueError):
    """Raised when a validation corpus cannot be loaded or is malformed."""


class ValidationDatasetLoader:
    """Loads a ``ValidationDataset`` from a corpus directory.

    Usage::

        loader = ValidationDatasetLoader()
        dataset = await loader.load("data/validation/example-corpus")
    """

    def __init__(
        self,
        *,
        examples_filename: str = "examples.jsonl",
        provenance_filename: str = "provenance.json",
    ) -> None:
        """Configure the loader's expected file names.

        Args:
            examples_filename: Name of the JSONL file with the examples.
            provenance_filename: Name of the optional provenance JSON file.
        """
        self._examples_filename = examples_filename
        self._provenance_filename = provenance_filename

    async def load(self, source: str) -> ValidationDataset:
        """Load and validate a validation corpus from a directory path.

        Args:
            source: Path to the corpus directory.

        Raises:
            ValidationDatasetLoadError: If the directory layout is invalid or
                any example record is malformed.
        """
        examples_path = os.path.join(source, self._examples_filename)
        provenance_path = os.path.join(source, self._provenance_filename)
        if not os.path.isfile(examples_path):
            msg = f"Validation corpus missing examples file: {examples_path}"
            raise ValidationDatasetLoadError(msg)

        provenance = DatasetProvenance()
        if os.path.isfile(provenance_path):
            provenance = await asyncio.to_thread(self._read_provenance, provenance_path)

        raw_lines = await asyncio.to_thread(self._read_lines, examples_path)
        records: list[tuple[int, dict[str, object]]] = []
        for line_number, line in enumerate(raw_lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                msg = f"Invalid JSON on line {line_number} of {examples_path}: {exc}"
                raise ValidationDatasetLoadError(msg) from exc
            if not isinstance(parsed, dict):
                msg = f"Line {line_number} of {examples_path} must be a JSON object"
                raise ValidationDatasetLoadError(msg)
            records.append((line_number, parsed))

        return load_validation_items(records, provenance=provenance)

    @staticmethod
    def _read_lines(path: str) -> list[str]:
        with open(path, encoding="utf-8") as handle:
            return handle.read().splitlines()

    @staticmethod
    def _read_provenance(path: str) -> DatasetProvenance:
        with open(path, encoding="utf-8") as handle:
            raw: object = json.load(handle)
        if not isinstance(raw, dict):
            msg = f"Validation provenance file must be an object: {path}"
            raise ValidationDatasetLoadError(msg)
        return DatasetProvenance.from_dict(raw)


def load_validation_items(
    records: Sequence[tuple[int, dict[str, object]]],
    *,
    provenance: DatasetProvenance | None = None,
) -> ValidationDataset:
    """Build and validate a ``ValidationDataset`` from JSONL records.

    This is the strict boundary for example records. Each record is a
    ``(line_number, mapping)`` tuple; line numbers drive clear error messages
    for malformed or duplicated examples.

    Args:
        records: Sequence of ``(line_number, example_mapping)`` pairs.
        provenance: Corpus-level provenance to attach (defaults to empty).

    Returns:
        A validated ``ValidationDataset``.

    Raises:
        ValidationDatasetLoadError: If any record is invalid or a duplicate id
            is detected.
    """
    corpus_provenance = provenance or DatasetProvenance()

    examples_raw: list[dict[str, object]] = []
    line_numbers: list[int] = []
    for line_number, record in records:
        examples_raw.append(dict(record))
        line_numbers.append(line_number)

    try:
        dataset = ValidationDataset.from_dict(
            {"provenance": corpus_provenance.to_dict(), "examples": examples_raw}
        )
    except ValueError as exc:
        msg = _first_line_message(line_numbers, exc)
        raise ValidationDatasetLoadError(msg) from exc

    # Duplicate detection with line-aware messages (ValidationDataset rejects
    # duplicates too, but with a corpus-level message).
    seen: dict[str, int] = {}
    for record, line_number in zip(examples_raw, line_numbers, strict=True):
        example_id = record.get("id")
        if example_id is None:
            continue
        key = str(example_id)
        if key in seen:
            msg = (
                f"Duplicate validation example id {key!r} (line {seen[key]} and line {line_number})"
            )
            raise ValidationDatasetLoadError(msg)
        seen[key] = line_number

    return dataset


def _first_line_message(line_numbers: list[int], cause: BaseException) -> str:
    if line_numbers:
        return f"Invalid validation record on line {line_numbers[0]}: {cause}"
    return f"Invalid validation record: {cause}"
