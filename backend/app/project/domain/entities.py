"""Project domain entity."""

from __future__ import annotations

from app.kernel.entities.base import AggregateRoot, UUIDv7, VersionMixin


class Project(AggregateRoot, VersionMixin):
    """Project aggregate root. Scopes resources within an Organization."""

    def __init__(
        self,
        *,
        entity_id: UUIDv7 | None = None,
        name: str,
        description: str | None = None,
        organization_id: str,
        created_by: str | None = None,
    ) -> None:
        super().__init__(entity_id=entity_id)
        VersionMixin.__init__(self)
        self._name = name.strip()
        self._description = (description or "").strip() or None
        self._organization_id = organization_id
        self._created_by = created_by
        self._is_active = True

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str | None:
        return self._description

    @property
    def organization_id(self) -> str:
        return self._organization_id

    @property
    def created_by(self) -> str | None:
        return self._created_by

    @property
    def is_active(self) -> bool:
        return self._is_active

    def update(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        if name is not None:
            self._name = name.strip()
        if description is not None:
            self._description = description.strip() or None
        self.touch()
        self.increment_version()

    def deactivate(self) -> None:
        self._is_active = False
        self.touch()
        self.increment_version()

    def activate(self) -> None:
        self._is_active = True
        self.touch()
        self.increment_version()

    @classmethod
    def create(
        cls,
        *,
        name: str,
        organization_id: str,
        description: str | None = None,
        created_by: str | None = None,
    ) -> Project:
        return cls(
            name=name,
            organization_id=organization_id,
            description=description,
            created_by=created_by,
        )
