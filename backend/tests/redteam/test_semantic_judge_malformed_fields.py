"""Regression tests for untrusted semantic judge JSON fields."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from app.redteam.engine.semantic_judge import SemanticEffectivenessJudge


@pytest.mark.parametrize("bad_verdict", ["", "UNKNOWN", "SUCCES", None])
def test_invalid_verdict_cannot_be_promoted_by_high_score(bad_verdict: object) -> None:
    judge = SemanticEffectivenessJudge()
    fallback = SimpleNamespace(score=0.5, confidence=0.5, reasoning="fallback")
    raw = (
        '{"verdict": '
        + ("null" if bad_verdict is None else '"' + str(bad_verdict) + '"')
        + ', "score": 0.99, "confidence": 0.9}'
    )
    parsed = judge._parse_semantic_verdict(raw, fallback)
    assert parsed["verdict"] == "INCONCLUSIVE"


@pytest.mark.parametrize(
    "bad_value", ["NaN", "Infinity", "-Infinity", "not-a-number", None, {}, []]
)
def test_malformed_score_and_confidence_are_finite(bad_value: object) -> None:
    import json

    judge = SemanticEffectivenessJudge()
    fallback = SimpleNamespace(score=0.4, confidence=0.6, reasoning="fallback")
    raw = json.dumps(
        {
            "verdict": "INCONCLUSIVE",
            "score": bad_value,
            "confidence": bad_value,
        }
    )
    parsed = judge._parse_semantic_verdict(raw, fallback)
    assert math.isfinite(parsed["score"])
    assert math.isfinite(parsed["confidence"])
    assert 0 <= parsed["score"] <= 1
    assert 0 <= parsed["confidence"] <= 1


def test_valid_semantic_verdict_is_preserved() -> None:
    judge = SemanticEffectivenessJudge()
    fallback = SimpleNamespace(score=0.5, confidence=0.5, reasoning="fallback")
    parsed = judge._parse_semantic_verdict(
        '{"verdict":"FAILURE","score":0.1,"confidence":0.95}', fallback
    )
    assert parsed["verdict"] == "FAILURE"
    assert parsed["score"] == 0.1
    assert parsed["confidence"] == 0.95
