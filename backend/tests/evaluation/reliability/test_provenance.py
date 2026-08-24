"""Tests for provenance and environment capture."""

from __future__ import annotations

from app.evaluation.reliability.provenance import (
    EnvironmentSnapshot,
    ReproducibilityContract,
    capture_environment,
    hash_requirements,
)


class TestEnvironmentSnapshot:
    def test_capture_returns_snapshot(self) -> None:
        snapshot = capture_environment()
        assert isinstance(snapshot, EnvironmentSnapshot)
        assert snapshot.python_version
        assert snapshot.platform_info

    def test_git_hash_is_string(self) -> None:
        snapshot = capture_environment()
        assert isinstance(snapshot.git_commit_hash, str)

    def test_git_branch_is_string(self) -> None:
        snapshot = capture_environment()
        assert isinstance(snapshot.git_branch, str)

    def test_requirements_hash_unknown_on_missing(self) -> None:
        h = hash_requirements("nonexistent_requirements_file.txt")
        assert h == "unknown"


class TestReproducibilityContract:
    def test_to_dict(self) -> None:
        env = EnvironmentSnapshot(
            git_commit_hash="abc123",
            git_branch="develop",
            python_version="3.12.0",
            requirements_hash="def456",
            platform_info="Linux",
        )
        contract = ReproducibilityContract(
            run_id="run-1",
            environment=env,
            evaluation_config_hash="cfg-hash",
            metric_versions={"correctness": "1.0.0"},
            provider_model="openai/gpt-4",
        )
        d = contract.to_dict()
        assert d["run_id"] == "run-1"
        assert d["environment"]["git_commit_hash"] == "abc123"
        assert d["metric_versions"]["correctness"] == "1.0.0"
        assert d["provider_model"] == "openai/gpt-4"
