"""Shared deterministic provider fakes for metric known-answer tests.

These fakes sit exactly at the provider boundary: they implement the
same call signatures as real providers but return scripted vectors
and verdicts so every metric score below has a hand-computable
expected value.
"""

from __future__ import annotations

import json
from typing import Any

from app.providers.models.enums import FinishReason
from app.providers.models.messages import Message
from app.providers.models.responses import ChatResponse, EmbeddingResponse, Usage

ALPHA = "alpha"
BETA = "beta"
GAMMA = "gamma"
DELTA = "delta"

ORTHOGONAL_VECTORS: dict[str, tuple[float, ...]] = {
    ALPHA: (1.0, 0.0, 0.0),
    BETA: (0.0, 1.0, 0.0),
    GAMMA: (1.0, 0.0, 0.0),
    DELTA: (1.0, 1.0, 0.0),
}


class ScriptedEmbeddingProvider:
    """Embedding provider returning precomputed vectors for known texts."""

    def __init__(
        self,
        vectors: dict[str, tuple[float, ...]] | None = None,
        *,
        model: str = "text-embedding-test",
    ) -> None:
        self._vectors = vectors if vectors is not None else ORTHOGONAL_VECTORS
        self._model = model
        self.embedded_texts: list[str] = []

    async def embed(
        self,
        texts: list[str],
        *,
        model: str,
        options: Any = None,
    ) -> EmbeddingResponse:
        text = texts[0]
        if text not in self._vectors:
            msg = f"No vector scripted for {text!r}"
            raise ValueError(msg)
        self.embedded_texts.append(text)
        vector = self._vectors[text]
        return EmbeddingResponse(
            model=self._model,
            provider="scripted-embedding",
            usage=Usage(input_tokens=1, output_tokens=0, total_tokens=1),
            finish_reason=FinishReason.STOP,
            embedding=vector,
            dimensions=len(vector),
        )


class ScriptedJudgeProvider:
    """Chat provider returning a scripted judge verdict.

    ``verdict`` may be a dict (serialized to JSON), a raw string, or
    an Exception instance to raise on call.
    """

    def __init__(
        self,
        verdict: dict[str, Any] | str | Exception,
        *,
        model: str = "judge-model",
        provider_name: str = "scripted-judge",
    ) -> None:
        self._verdict = verdict
        self._model = model
        self.provider_name = provider_name
        self.calls = 0

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str = "",
        options: Any = None,
    ) -> ChatResponse:
        self.calls += 1
        if isinstance(self._verdict, Exception):
            raise self._verdict
        content = json.dumps(self._verdict) if isinstance(self._verdict, dict) else self._verdict
        return ChatResponse(
            content=content,
            model=model or self._model,
            provider=self.provider_name,
            usage=Usage(input_tokens=20, output_tokens=10, total_tokens=30),
            finish_reason=FinishReason.STOP,
        )
