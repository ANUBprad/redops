"""Tests for evaluation definition value objects."""

from __future__ import annotations

import pytest

from app.evaluation.domain.value_objects.evaluation_definition_vos import (
    EvaluationDescription,
    EvaluationName,
    MetricId,
    ProviderId,
)


class TestEvaluationName:
    """Tests for EvaluationName value object."""

    def test_valid_name(self) -> None:
        """A valid name is accepted."""
        name = EvaluationName(value="My Evaluation")
        assert name.value == "My Evaluation"

    def test_strips_whitespace(self) -> None:
        """Name preserves original value (no auto-strip)."""
        name = EvaluationName(value="  trimmed  ")
        assert name.value == "  trimmed  "

    def test_empty_name_raises(self) -> None:
        """Empty or whitespace-only name raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            EvaluationName(value="")

    def test_whitespace_only_name_raises(self) -> None:
        """Whitespace-only name raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            EvaluationName(value="   ")

    def test_too_long_name_raises(self) -> None:
        """Name exceeding 255 characters raises ValueError."""
        with pytest.raises(ValueError, match="cannot exceed 255"):
            EvaluationName(value="x" * 256)

    def test_exactly_255_chars(self) -> None:
        """Name of exactly 255 characters is accepted."""
        name = EvaluationName(value="x" * 255)
        assert len(name.value) == 255

    def test_frozen(self) -> None:
        """Name is immutable."""
        name = EvaluationName(value="test")
        with pytest.raises(AttributeError):
            name.value = "changed"  # type: ignore[misc]


class TestEvaluationDescription:
    """Tests for EvaluationDescription value object."""

    def test_none_description(self) -> None:
        """None description is valid."""
        desc = EvaluationDescription()
        assert desc.value is None

    def test_valid_description(self) -> None:
        """A valid description is accepted."""
        desc = EvaluationDescription(value="A test description")
        assert desc.value == "A test description"

    def test_too_long_description_raises(self) -> None:
        """Description exceeding 2000 characters raises ValueError."""
        with pytest.raises(ValueError, match="cannot exceed 2000"):
            EvaluationDescription(value="x" * 2001)

    def test_exactly_2000_chars(self) -> None:
        """Description of exactly 2000 characters is accepted."""
        desc = EvaluationDescription(value="x" * 2000)
        assert len(desc.value) == 2000  # type: ignore[arg-type]

    def test_frozen(self) -> None:
        """Description is immutable."""
        desc = EvaluationDescription(value="test")
        with pytest.raises(AttributeError):
            desc.value = "changed"  # type: ignore[misc]


class TestMetricId:
    """Tests for MetricId value object."""

    def test_valid_metric_id(self) -> None:
        """A valid metric ID is accepted."""
        m = MetricId(value="accuracy")
        assert m.value == "accuracy"

    def test_empty_metric_id_raises(self) -> None:
        """Empty metric ID raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            MetricId(value="")

    def test_whitespace_only_metric_id_raises(self) -> None:
        """Whitespace-only metric ID raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            MetricId(value="   ")


class TestProviderId:
    """Tests for ProviderId value object."""

    def test_valid_provider_id(self) -> None:
        """A valid provider ID is accepted."""
        p = ProviderId(value="openai")
        assert p.value == "openai"

    def test_empty_provider_id_raises(self) -> None:
        """Empty provider ID raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            ProviderId(value="")

    def test_whitespace_only_provider_id_raises(self) -> None:
        """Whitespace-only provider ID raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            ProviderId(value="   ")
