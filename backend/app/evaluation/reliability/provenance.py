"""Environment capture for reproducibility.

Records the execution environment so evaluation results can be traced
back to the exact code, dependencies, and configuration that produced
them. Secrets are never captured.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class EnvironmentSnapshot:
    """Immutable capture of the execution environment."""

    git_commit_hash: str = "unknown"
    git_branch: str = "unknown"
    python_version: str = "unknown"
    requirements_hash: str = "unknown"
    platform_info: str = "unknown"


def capture_git_hash() -> str:
    """Return the current git commit hash, or 'unknown' on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def capture_git_branch() -> str:
    """Return the current git branch, or 'unknown' on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def hash_requirements(requirements_path: str = "requirements.txt") -> str:
    """Hash a requirements file for dependency fingerprinting.

    Returns 'unknown' if the file cannot be read.
    """
    try:
        import pathlib

        text = pathlib.Path(requirements_path).read_text(encoding="utf-8")
        return hashlib.sha256(text.encode()).hexdigest()[:16]
    except (FileNotFoundError, OSError):
        return "unknown"


def capture_environment() -> EnvironmentSnapshot:
    """Capture the current execution environment."""
    import platform
    import sys

    return EnvironmentSnapshot(
        git_commit_hash=capture_git_hash(),
        git_branch=capture_git_branch(),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        requirements_hash=hash_requirements(),
        platform_info=platform.platform(),
    )


@dataclass(frozen=True, slots=True)
class ReproducibilityContract:
    """Describes what must be known to reproduce an evaluation result."""

    run_id: str
    environment: EnvironmentSnapshot
    evaluation_config_hash: str
    dataset_hash: str = ""
    metric_versions: dict[str, str] = field(default_factory=dict)
    provider_model: str = ""
    judge_model: str = ""
    embedding_model: str = ""

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "run_id": self.run_id,
            "environment": {
                "git_commit_hash": self.environment.git_commit_hash,
                "git_branch": self.environment.git_branch,
                "python_version": self.environment.python_version,
                "requirements_hash": self.environment.requirements_hash,
                "platform_info": self.environment.platform_info,
            },
            "evaluation_config_hash": self.evaluation_config_hash,
            "dataset_hash": self.dataset_hash,
            "metric_versions": self.metric_versions,
            "provider_model": self.provider_model,
            "judge_model": self.judge_model,
            "embedding_model": self.embedding_model,
        }
