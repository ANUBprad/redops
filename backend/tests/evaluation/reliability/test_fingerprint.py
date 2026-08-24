"""Tests for deterministic evaluation fingerprinting."""

from __future__ import annotations

from app.evaluation.reliability.fingerprint import (
    compute_fingerprint,
    compute_input_hash,
)


class TestFingerprintDeterminism:
    def test_same_config_produces_same_fingerprint(self) -> None:
        fp1 = compute_fingerprint(
            prompt_template="summarize",
            provider="openai",
            model="gpt-4",
            metrics=("correctness", "coherence"),
        )
        fp2 = compute_fingerprint(
            prompt_template="summarize",
            provider="openai",
            model="gpt-4",
            metrics=("correctness", "coherence"),
        )
        assert fp1.fingerprint == fp2.fingerprint

    def test_different_model_produces_different_fingerprint(self) -> None:
        fp1 = compute_fingerprint(model="gpt-4", metrics=("correctness",))
        fp2 = compute_fingerprint(model="gpt-3.5", metrics=("correctness",))
        assert fp1.fingerprint != fp2.fingerprint

    def test_different_metrics_produces_different_fingerprint(self) -> None:
        fp1 = compute_fingerprint(metrics=("correctness",))
        fp2 = compute_fingerprint(metrics=("coherence",))
        assert fp1.fingerprint != fp2.fingerprint

    def test_different_provider_produces_different_fingerprint(self) -> None:
        fp1 = compute_fingerprint(provider="openai", model="gpt-4")
        fp2 = compute_fingerprint(provider="anthropic", model="gpt-4")
        assert fp1.fingerprint != fp2.fingerprint

    def test_different_temperature_produces_different_fingerprint(self) -> None:
        fp1 = compute_fingerprint(model="gpt-4", temperature=0.0)
        fp2 = compute_fingerprint(model="gpt-4", temperature=0.7)
        assert fp1.fingerprint != fp2.fingerprint

    def test_different_judge_model_produces_different_fingerprint(self) -> None:
        fp1 = compute_fingerprint(judge_model="gpt-4")
        fp2 = compute_fingerprint(judge_model="gpt-3.5")
        assert fp1.fingerprint != fp2.fingerprint

    def test_different_embedding_model_produces_different_fingerprint(self) -> None:
        fp1 = compute_fingerprint(embedding_model="text-embedding-3-small")
        fp2 = compute_fingerprint(embedding_model="text-embedding-3-large")
        assert fp1.fingerprint != fp2.fingerprint

    def test_different_prompt_template_produces_different_fingerprint(self) -> None:
        fp1 = compute_fingerprint(prompt_template="v1")
        fp2 = compute_fingerprint(prompt_template="v2")
        assert fp1.fingerprint != fp2.fingerprint

    def test_fingerprint_length(self) -> None:
        fp = compute_fingerprint(model="gpt-4")
        assert len(fp.fingerprint) == 32

    def test_components_recorded(self) -> None:
        fp = compute_fingerprint(
            provider="openai",
            model="gpt-4",
            metrics=("correctness", "coherence"),
        )
        assert fp.components["provider"] == "openai"
        assert fp.components["model"] == "gpt-4"


class TestFingerprintMatches:
    def test_matches_same(self) -> None:
        fp1 = compute_fingerprint(model="gpt-4")
        fp2 = compute_fingerprint(model="gpt-4")
        assert fp1.matches(fp2)

    def test_matches_different(self) -> None:
        fp1 = compute_fingerprint(model="gpt-4")
        fp2 = compute_fingerprint(model="gpt-3.5")
        assert not fp1.matches(fp2)


class TestInputHash:
    def test_same_inputs_same_hash(self) -> None:
        h1 = compute_input_hash("prompt", "response", "ref", "ctx")
        h2 = compute_input_hash("prompt", "response", "ref", "ctx")
        assert h1 == h2

    def test_different_inputs_different_hash(self) -> None:
        h1 = compute_input_hash("prompt1", "response")
        h2 = compute_input_hash("prompt2", "response")
        assert h1 != h2

    def test_hash_length(self) -> None:
        h = compute_input_hash("test")
        assert len(h) == 32
