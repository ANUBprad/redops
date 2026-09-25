"""Evaluation Profile aggregate root.

Represents a reusable evaluation configuration template that defines
metrics, thresholds, providers, concurrency, and timeouts. System
profiles are built-in and read-only; custom profiles are user-managed.
"""

from __future__ import annotations

from typing import Any

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
from app.kernel.entities.base import AggregateRoot, UUIDv7, VersionMixin
from app.kernel.exceptions.errors import ConflictError


class EvaluationProfileEntity(AggregateRoot, VersionMixin):
    """Evaluation profile aggregate root.

    A profile is a reusable configuration template stored in the database.
    System profiles (is_builtin=True) are read-only and cannot be deleted.
    """

    def __init__(
        self,
        *,
        entity_id: UUIDv7 | None = None,
        project_id: str,
        name: ProfileName,
        description: ProfileDescription | None = None,
        scope: ProfileScope = ProfileScope.CUSTOM,
        configuration: dict[str, Any] | None = None,
        is_builtin: bool = False,
    ) -> None:
        """Initialize an evaluation profile.

        Args:
            entity_id: Optional UUIDv7 identifier.
            project_id: The project this profile belongs to.
            name: Validated profile name.
            description: Optional validated description.
            scope: Profile scope (system, project, custom).
            configuration: Profile configuration (metrics, thresholds, etc.).
            is_builtin: Whether this is a built-in system profile.

        """
        super().__init__(entity_id=entity_id)
        VersionMixin.__init__(self)
        self._project_id = project_id
        self._name = name
        self._description = description
        self._scope = scope
        self._configuration = configuration or {}
        self._is_builtin = is_builtin

    @property
    def project_id(self) -> str:
        """Return the project identifier."""
        return self._project_id

    @property
    def name(self) -> ProfileName:
        """Return the profile name."""
        return self._name

    @property
    def description(self) -> ProfileDescription | None:
        """Return the profile description."""
        return self._description

    @property
    def scope(self) -> ProfileScope:
        """Return the profile scope."""
        return self._scope

    @property
    def configuration(self) -> dict[str, Any]:
        """Return the profile configuration."""
        return self._configuration

    @property
    def is_builtin(self) -> bool:
        """Return whether this is a built-in system profile."""
        return self._is_builtin

    def update(
        self,
        *,
        name: ProfileName | None = None,
        description: ProfileDescription | None = None,
        configuration: dict[str, Any] | None = None,
    ) -> None:
        """Update profile fields.

        System profiles can only have their configuration updated.

        Args:
            name: New name, or None to keep current.
            description: New description, or None to keep current.
            configuration: New configuration, or None to keep current.

        Raises:
            ConflictError: If trying to rename a system profile.

        """
        if self._is_builtin and name is not None:
            raise ConflictError(
                message="System profile names cannot be changed",
                details={"profile_id": str(self.id)},
            )
        if name is not None:
            self._name = name
        if description is not None:
            self._description = description
        if configuration is not None:
            self._configuration = configuration
        self.touch()
        self.increment_version()
        self.raise_event(
            ProfileUpdated(
                profile_id=self.id,
                project_id=self._project_id,
                name=str(self._name.value),
                correlation_id=str(self.id),
            ),
        )

    def delete(self) -> None:
        """Mark profile for deletion.

        Raises:
            ConflictError: If this is a built-in system profile.

        """
        if self._is_builtin:
            raise ConflictError(
                message="System profiles cannot be deleted",
                details={"profile_id": str(self.id)},
            )
        self.raise_event(
            ProfileDeleted(
                profile_id=self.id,
                project_id=self._project_id,
                correlation_id=str(self.id),
            ),
        )

    def resolve_configuration(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        """Resolve the effective configuration, merging with overrides.

        Args:
            overrides: Optional run-time overrides to merge.

        Returns:
            The resolved configuration dictionary.

        """
        resolved = dict(self._configuration)
        if overrides:
            resolved.update(overrides)
        return resolved

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        name: ProfileName,
        description: ProfileDescription | None = None,
        scope: ProfileScope = ProfileScope.CUSTOM,
        configuration: dict[str, Any] | None = None,
        is_builtin: bool = False,
    ) -> EvaluationProfileEntity:
        """Factory method to create a new evaluation profile.

        Args:
            project_id: The project identifier.
            name: Validated profile name.
            description: Optional description.
            scope: Profile scope.
            configuration: Profile configuration.
            is_builtin: Whether this is a built-in profile.

        Returns:
            A new EvaluationProfileEntity.

        """
        profile = cls(
            project_id=project_id,
            name=name,
            description=description,
            scope=scope,
            configuration=configuration,
            is_builtin=is_builtin,
        )
        profile.raise_event(
            ProfileCreated(
                profile_id=profile.id,
                project_id=project_id,
                name=str(name.value),
                correlation_id=str(profile.id),
            ),
        )
        return profile
