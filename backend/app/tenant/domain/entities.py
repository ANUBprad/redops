"""Tenant domain entities: Organization, Membership, Invitation."""

from __future__ import annotations

from datetime import UTC, datetime

from app.kernel.entities.base import AggregateRoot, Entity, UUIDv7, VersionMixin
from app.tenant.domain.enums import InvitationStatus, OrganizationRole


class Organization(AggregateRoot, VersionMixin):
    """Organization aggregate root. Top-level tenant boundary."""

    def __init__(
        self,
        *,
        entity_id: UUIDv7 | None = None,
        name: str,
        slug: str,
        description: str | None = None,
        owner_id: str,
    ) -> None:
        super().__init__(entity_id=entity_id)
        VersionMixin.__init__(self)
        self._name = name.strip()
        self._slug = slug.lower().strip()
        self._description = (description or "").strip() or None
        self._owner_id = owner_id
        self._is_active = True

    @property
    def name(self) -> str:
        return self._name

    @property
    def slug(self) -> str:
        return self._slug

    @property
    def description(self) -> str | None:
        return self._description

    @property
    def owner_id(self) -> str:
        return self._owner_id

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
        slug: str,
        owner_id: str,
        description: str | None = None,
    ) -> Organization:
        return cls(
            name=name,
            slug=slug,
            description=description,
            owner_id=owner_id,
        )


class Membership(Entity):
    """Membership linking a User to an Organization with a role."""

    def __init__(
        self,
        *,
        entity_id: UUIDv7 | None = None,
        user_id: str,
        organization_id: str,
        role: OrganizationRole = OrganizationRole.MEMBER,
        invited_by: str | None = None,
        joined_at: datetime | None = None,
    ) -> None:
        super().__init__(entity_id=entity_id)
        self._user_id = user_id
        self._organization_id = organization_id
        self._role = role
        self._invited_by = invited_by
        self._joined_at = joined_at or datetime.now(UTC)
        self._is_active = True

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def organization_id(self) -> str:
        return self._organization_id

    @property
    def role(self) -> OrganizationRole:
        return self._role

    @property
    def invited_by(self) -> str | None:
        return self._invited_by

    @property
    def joined_at(self) -> datetime:
        return self._joined_at

    @property
    def is_active(self) -> bool:
        return self._is_active

    def change_role(self, new_role: OrganizationRole) -> None:
        self._role = new_role
        self.touch()

    def deactivate(self) -> None:
        self._is_active = False
        self.touch()

    def activate(self) -> None:
        self._is_active = True
        self.touch()


class Invitation(Entity):
    """Invitation to join an Organization."""

    def __init__(
        self,
        *,
        entity_id: UUIDv7 | None = None,
        email: str,
        organization_id: str,
        role: OrganizationRole = OrganizationRole.MEMBER,
        invited_by: str,
        status: InvitationStatus = InvitationStatus.PENDING,
        expires_at: datetime | None = None,
    ) -> None:
        super().__init__(entity_id=entity_id)
        self._email = email.lower().strip()
        self._organization_id = organization_id
        self._role = role
        self._invited_by = invited_by
        self._status = status
        self._expires_at = expires_at or (
            datetime.now(UTC).replace(microsecond=0) + __import__("datetime").timedelta(days=7)
        )

    @property
    def email(self) -> str:
        return self._email

    @property
    def organization_id(self) -> str:
        return self._organization_id

    @property
    def role(self) -> OrganizationRole:
        return self._role

    @property
    def invited_by(self) -> str:
        return self._invited_by

    @property
    def status(self) -> InvitationStatus:
        return self._status

    @property
    def expires_at(self) -> datetime:
        return self._expires_at

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) > self._expires_at

    @property
    def is_valid(self) -> bool:
        return self._status == InvitationStatus.PENDING and not self.is_expired

    def accept(self) -> None:
        if not self.is_valid:
            from app.kernel.exceptions.errors import ConflictError

            raise ConflictError(
                message="Invitation is not valid",
                details={"invitation_id": str(self.id), "status": self._status.value},
            )
        self._status = InvitationStatus.ACCEPTED
        self.touch()

    def revoke(self) -> None:
        if self._status == InvitationStatus.ACCEPTED:
            from app.kernel.exceptions.errors import ConflictError

            raise ConflictError(message="Cannot revoke an accepted invitation")
        self._status = InvitationStatus.REVOKED
        self.touch()

    def expire(self) -> None:
        if self._status == InvitationStatus.PENDING:
            self._status = InvitationStatus.EXPIRED
            self.touch()
