"""Fixture invariant tests: the canonical items must stay honest."""

from __future__ import annotations

import json

from tests.evaluation.fixtures.canonical_items import (
    CANONICAL_ITEMS,
    get_item,
)


class TestCanonicalItemInvariants:
    """Structural guarantees for the shared fixture set."""

    def test_exactly_eight_canonical_cases(self) -> None:
        assert len(CANONICAL_ITEMS) == 8

    def test_keys_are_unique(self) -> None:
        keys = [item.key for item in CANONICAL_ITEMS]
        assert len(keys) == len(set(keys))

    def test_all_responses_non_empty(self) -> None:
        assert all(item.response.strip() for item in CANONICAL_ITEMS)

    def test_expected_valid_json_actually_parses(self) -> None:
        for item in CANONICAL_ITEMS:
            if item.expect_valid_json:
                parsed = json.loads(item.response)
                assert isinstance(parsed, dict)

    def test_structured_items_carry_schema(self) -> None:
        for item in CANONICAL_ITEMS:
            if item.expect_valid_json:
                assert item.schema is not None
                assert "answer" in item.schema["required"]

    def test_hallucination_pair_differs_only_in_fabrication(self) -> None:
        grounded = get_item("context_grounded")
        ungrounded = get_item("ungrounded")
        hallucinated = get_item("hallucinated_answer")

        # all three share a context-bearing or reference-bearing setup
        assert grounded.context and ungrounded.context
        assert hallucinated.context
        assert "lunar gravity" in ungrounded.response
        assert "12 million" in hallucinated.response
