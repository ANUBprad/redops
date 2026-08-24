"""Deterministic evaluation fingerprinting.

Computes a stable SHA-256 fingerprint that identifies the meaningful
evaluation configuration. The same logical configuration always
produces the same fingerprint; different configurations produce
different fingerprints.

Excludes timestamps, database IDs, random request IDs, and other
transient runtime data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def _canonical_json(obj: object) -> str:
    """Produce a deterministic JSON string for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _hash_content(content: str) -> str:
    """SHA-256 hash truncated to 32 hex characters."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True, slots=True)
class EvaluationFingerprint:
    """Stable identifier for an evaluation configuration."""

    fingerprint: str
    components: dict[str, str]

    def matches(self, other: EvaluationFingerprint) -> bool:
        """Return True if two fingerprints are identical."""
        return self.fingerprint == other.fingerprint


def compute_fingerprint(
    *,
    prompt_template: str = "",
    system_prompt: str = "",
    provider: str = "",
    model: str = "",
    metrics: tuple[str, ...] = (),
    metric_versions: dict[str, str] | None = None,
    judge_provider: str = "",
    judge_model: str = "",
    judge_prompt_version: str = "",
    embedding_provider: str = "",
    embedding_model: str = "",
    dataset_hash: str = "",
    temperature: float = 0.0,
    max_tokens: int = 4096,
    extra_config: dict[str, str] | None = None,
) -> EvaluationFingerprint:
    """Compute a deterministic fingerprint for an evaluation configuration.

    Every parameter that meaningfully changes the evaluation output
    contributes to the fingerprint. Timestamps, database IDs, and
    transient metadata are excluded.
    """
    components: dict[str, str] = {}

    components["prompt_template"] = _hash_content(prompt_template) if prompt_template else ""
    components["system_prompt"] = _hash_content(system_prompt) if system_prompt else ""
    components["provider"] = provider
    components["model"] = model
    components["metrics"] = _canonical_json(sorted(metrics))
    components["metric_versions"] = _canonical_json(metric_versions) if metric_versions else ""
    components["judge_provider"] = judge_provider
    components["judge_model"] = judge_model
    components["judge_prompt_version"] = judge_prompt_version
    components["embedding_provider"] = embedding_provider
    components["embedding_model"] = embedding_model
    components["dataset_hash"] = dataset_hash
    components["temperature"] = str(temperature)
    components["max_tokens"] = str(max_tokens)

    if extra_config:
        components["extra_config"] = _canonical_json(extra_config)

    canonical = _canonical_json(components)
    fingerprint_value = _hash_content(canonical)

    return EvaluationFingerprint(
        fingerprint=fingerprint_value,
        components=components,
    )


def compute_input_hash(
    prompt: str,
    response: str = "",
    reference: str = "",
    context: str = "",
) -> str:
    """Compute a content hash for evaluation inputs.

    Used for deduplication and change detection without storing
    the full content.
    """
    parts = [prompt, response, reference, context]
    canonical = _canonical_json(parts)
    return _hash_content(canonical)
