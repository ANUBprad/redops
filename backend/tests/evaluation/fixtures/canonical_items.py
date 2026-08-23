"""Realistic, deterministic evaluation fixtures.

Eight canonical evaluation items covering the primary failure modes
RedOps scoring must distinguish. All content is synthetic and
version-controlled — no real user data, no randomness, no network.
These are the shared inputs for metric known-answer and integration
tests.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CanonicalItem:
    """A single canonical evaluation case."""

    key: str
    description: str
    prompt: str
    response: str
    reference: str = ""
    context: str = ""
    schema: dict | None = None

    #: expected json_validity score (1.0 / 0.0)
    expect_valid_json: bool = False


STRUCTURED_SCHEMA: dict = {
    "type": "object",
    "required": ["answer"],
    "properties": {"answer": {"type": "string"}},
}

CANONICAL_ITEMS: tuple[CanonicalItem, ...] = (
    CanonicalItem(
        key="correct_answer",
        description="Response factually matches the reference answer.",
        prompt="What is the capital of France?",
        response="Paris is the capital of France.",
        reference="Paris is the capital of France.",
        expect_valid_json=False,
    ),
    CanonicalItem(
        key="incorrect_answer",
        description="Response asserts a factually wrong answer.",
        prompt="What is the capital of France?",
        response="The capital of France is Berlin.",
        reference="Paris is the capital of France.",
        expect_valid_json=False,
    ),
    CanonicalItem(
        key="irrelevant_answer",
        description="Response answers a different question entirely.",
        prompt="What is the capital of France?",
        response=(
            "To bake a classic apple pie, peel and slice five apples, "
            "mix with cinnamon and sugar, and bake for 45 minutes at 190C."
        ),
        reference="Paris is the capital of France.",
        expect_valid_json=False,
    ),
    CanonicalItem(
        key="hallucinated_answer",
        description="Grounded core plus an unsupported fabricated statistic.",
        prompt="Summarize what the context says about Paris.",
        response=(
            "Paris is the capital of France. It has exactly 12 million "
            "registered bicycles as of last Tuesday."
        ),
        reference="",
        context="Paris is the capital of France. It is known for the Eiffel Tower.",
        expect_valid_json=False,
    ),
    CanonicalItem(
        key="valid_structured",
        description="Well-formed JSON conforming to the structured schema.",
        prompt='Answer as JSON: {"answer": <your answer>}. What is the capital of France?',
        response='{"answer": "Paris"}',
        reference='{"answer": "Paris"}',
        schema=STRUCTURED_SCHEMA,
        expect_valid_json=True,
    ),
    CanonicalItem(
        key="invalid_structured",
        description="JSON missing the required 'answer' field.",
        prompt='Answer as JSON: {"answer": <your answer>}. What is the capital of France?',
        response='{"city": "Paris", "confidence": 0.4}',
        reference='{"answer": "Paris"}',
        schema=STRUCTURED_SCHEMA,
        expect_valid_json=True,
    ),
    CanonicalItem(
        key="context_grounded",
        description="Every claim in the response is supported by the context.",
        prompt="According to the context, what powers the water cycle?",
        response="The water cycle is driven by solar energy causing evaporation.",
        context=(
            "The water cycle describes how water moves through the environment. "
            "Solar energy drives evaporation from oceans into the atmosphere."
        ),
        expect_valid_json=False,
    ),
    CanonicalItem(
        key="ungrounded",
        description="Response introduces claims absent from the context.",
        prompt="According to the context, what powers the water cycle?",
        response=(
            "The water cycle is powered by lunar gravity pulling ocean "
            "water into clouds twice a day."
        ),
        context=(
            "The water cycle describes how water moves through the environment. "
            "Solar energy drives evaporation from oceans into the atmosphere."
        ),
        expect_valid_json=False,
    ),
)


def get_item(key: str) -> CanonicalItem:
    """Return the canonical item with the given key."""
    for item in CANONICAL_ITEMS:
        if item.key == key:
            return item
    msg = f"Unknown canonical item: {key}"
    raise KeyError(msg)
