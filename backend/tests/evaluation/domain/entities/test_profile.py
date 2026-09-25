"""Tests for the Evaluation Profile aggregate."""

from __future__ import annotations

import pytest

from app.evaluation.domain.entities.profile import EvaluationProfileEntity
from app.evaluation.domain.enums.profile_enums import ProfileScope
from app.evaluation.domain.events.profile_events import (
    ProfileCreated,
    ProfileDeleted,
    ProfileUpdated,
)
from app.evaluation.domain.value_objects.profile_value_objects import (
    ProfileDescription,
    ProfileName,
)
from app.kernel.exceptions.errors import ConflictError


def _make_profile(
    *,
    name: str = "test-profile",
    project_id: str = "proj-1",
    is_builtin: bool = False,
) -> EvaluationProfileEntity:
    """Create a minimal EvaluationProfileEntity for testing."""
    return EvaluationProfileEntity.create(
        project_id=project_id,
        name=ProfileName(value=name),
        scope=ProfileScope.SYSTEM if is_builtin else ProfileScope.CUSTOM,
        is_builtin=is_builtin,
    )


class TestProfileCreate:
    """Tests for EvaluationProfileEntity.create factory method."""

    def test_create_raises_event(self) -> None:
        profile = _make_profile()
        events = profile.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], ProfileCreated)

    def test_create_sets_custom_scope(self) -> None:
        profile = _make_profile()
        assert profile.scope == ProfileScope.CUSTOM
        assert not profile.is_builtin

    def test_create_builtin(self) -> None:
        profile = _make_profile(is_builtin=True)
        assert profile.scope == ProfileScope.SYSTEM
        assert profile.is_builtin

    def test_create_with_configuration(self) -> None:
        profile = EvaluationProfileEntity.create(
            project_id="proj-1",
            name=ProfileName(value="safety"),
            configuration={"metrics": ["toxicity"], "thresholds": {"toxicity": {"lte": 0.1}}},
        )
        assert profile.configuration["metrics"] == ["toxicity"]

    def test_create_requires_name(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            EvaluationProfileEntity.create(
                project_id="proj-1",
                name=ProfileName(value=""),
            )


class TestProfileUpdate:
    """Tests for profile update behavior."""

    def test_update_custom_profile(self) -> None:
        profile = _make_profile()
        profile.update(name=ProfileName(value="new-name"))
        assert str(profile.name.value) == "new-name"

    def test_update_builtin_name_raises(self) -> None:
        profile = _make_profile(is_builtin=True)
        with pytest.raises(ConflictError, match="System profile names cannot be changed"):
            profile.update(name=ProfileName(value="new-name"))

    def test_update_builtin_configuration_allowed(self) -> None:
        profile = _make_profile(is_builtin=True)
        profile.update(configuration={"metrics": ["toxicity"]})
        assert profile.configuration["metrics"] == ["toxicity"]

    def test_update_raises_event(self) -> None:
        profile = _make_profile()
        profile.update(description=ProfileDescription(value="Updated"))
        events = profile.collect_events()
        assert any(isinstance(e, ProfileUpdated) for e in events)


class TestProfileDelete:
    """Tests for profile delete behavior."""

    def test_delete_custom_profile(self) -> None:
        profile = _make_profile()
        profile.delete()
        events = profile.collect_events()
        assert any(isinstance(e, ProfileDeleted) for e in events)

    def test_delete_builtin_raises(self) -> None:
        profile = _make_profile(is_builtin=True)
        with pytest.raises(ConflictError, match="System profiles cannot be deleted"):
            profile.delete()


class TestProfileResolve:
    """Tests for configuration resolution."""

    def test_resolve_no_overrides(self) -> None:
        profile = _make_profile()
        profile.update(configuration={"metrics": ["toxicity"], "concurrency": 5})
        resolved = profile.resolve_configuration()
        assert resolved["metrics"] == ["toxicity"]
        assert resolved["concurrency"] == 5

    def test_resolve_with_overrides(self) -> None:
        profile = _make_profile()
        profile.update(configuration={"metrics": ["toxicity"], "concurrency": 5})
        resolved = profile.resolve_configuration({"concurrency": 10})
        assert resolved["concurrency"] == 10
        assert resolved["metrics"] == ["toxicity"]
