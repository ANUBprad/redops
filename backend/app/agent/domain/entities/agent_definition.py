"""Agent definition aggregate root.

Represents a registered agent configuration that can be assigned
to evaluation runs. Manages its own lifecycle (ACTIVE, INACTIVE, ERROR, ARCHIVED)
and raises domain events on mutations.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.agent.domain.enums.agent_enums import AgentStatus, AgentType
from app.agent.domain.events.agent_events import (
    AgentDefinitionActivated,
    AgentDefinitionArchived,
    AgentDefinitionCreated,
    AgentDefinitionDeactivated,
    AgentDefinitionDeleted,
    AgentDefinitionUpdated,
)
from app.agent.domain.value_objects.agent_vos import (
    AgentDescription,
    AgentEndpoint,
    AgentName,
)
from app.kernel.entities.base import AggregateRoot, UUIDv7, VersionMixin
from app.kernel.exceptions.errors import ConflictError, ValidationError


class AgentDefinition(AggregateRoot, VersionMixin):
    """Agent definition aggregate root.

    Encapsulates a saved agent configuration including its
    name, type, model, provider, capabilities, and config.
    Enforces lifecycle invariants and raises domain events on mutations.
    """

    def __init__(
        self,
        *,
        entity_id: UUIDv7 | None = None,
        project_id: str,
        name: AgentName,
        description: AgentDescription | None = None,
        agent_type: AgentType,
        model: str,
        provider: str,
        capabilities: tuple[str, ...] = (),
        config: dict[str, Any] | None = None,
        endpoint: AgentEndpoint | None = None,
        status: AgentStatus = AgentStatus.ACTIVE,
        created_by: str | None = None,
    ) -> None:
        """Initialize an agent definition.

        Args:
            entity_id: Optional UUIDv7 identifier.
            project_id: The project this agent belongs to.
            name: Validated agent name.
            description: Optional validated description.
            agent_type: The type of agent.
            model: Model identifier string.
            provider: Provider identifier string.
            capabilities: Tuple of capability/skill tags.
            config: Optional model configuration (temperature, max_tokens, etc.).
            endpoint: Optional custom endpoint URL.
            status: Initial lifecycle status.
            created_by: Optional creator identifier.

        """
        super().__init__(entity_id=entity_id)
        VersionMixin.__init__(self)
        self._project_id = project_id
        self._name = name
        self._description = description
        self._agent_type = agent_type
        self._model = model
        self._provider = provider
        self._capabilities = capabilities
        self._config = config or {}
        self._endpoint = endpoint
        self._status = status
        self._created_by = created_by

    @property
    def project_id(self) -> str:
        """Return the project identifier."""
        return self._project_id

    @property
    def name(self) -> AgentName:
        """Return the agent name."""
        return self._name

    @property
    def description(self) -> AgentDescription | None:
        """Return the agent description."""
        return self._description

    @property
    def agent_type(self) -> AgentType:
        """Return the agent type."""
        return self._agent_type

    @property
    def model(self) -> str:
        """Return the model identifier."""
        return self._model

    @property
    def provider(self) -> str:
        """Return the provider identifier."""
        return self._provider

    @property
    def capabilities(self) -> tuple[str, ...]:
        """Return the capability tags."""
        return self._capabilities

    @property
    def config(self) -> Mapping[str, Any]:
        """Return the model configuration as an immutable view."""
        return self._config

    @property
    def endpoint(self) -> AgentEndpoint | None:
        """Return the custom endpoint."""
        return self._endpoint

    @property
    def status(self) -> AgentStatus:
        """Return the lifecycle status."""
        return self._status

    @property
    def created_by(self) -> str | None:
        """Return the creator identifier."""
        return self._created_by

    def update(
        self,
        *,
        name: AgentName | None = None,
        description: AgentDescription | None = None,
        agent_type: AgentType | None = None,
        model: str | None = None,
        provider: str | None = None,
        capabilities: tuple[str, ...] | None = None,
        config: dict[str, Any] | None = None,
        endpoint: AgentEndpoint | None = None,
    ) -> None:
        """Update agent definition fields.

        Only ACTIVE or INACTIVE agents can be updated.

        Args:
            name: New name, or None to keep current.
            description: New description, or None to keep current.
            agent_type: New type, or None to keep current.
            model: New model, or None to keep current.
            provider: New provider, or None to keep current.
            capabilities: New capabilities, or None to keep current.
            config: New config, or None to keep current.
            endpoint: New endpoint, or None to keep current.

        Raises:
            ConflictError: If the agent is ARCHIVED.

        """
        if not self._status.is_editable:
            raise ConflictError(
                message="Archived agents cannot be updated",
                details={"agent_id": str(self.id), "status": self._status.value},
            )
        if name is not None:
            self._name = name
        if description is not None:
            self._description = description
        if agent_type is not None:
            self._agent_type = agent_type
        if model is not None:
            self._model = model
        if provider is not None:
            self._provider = provider
        if capabilities is not None:
            self._capabilities = capabilities
        if config is not None:
            self._config = config
        if endpoint is not None:
            self._endpoint = endpoint
        self.touch()
        self.increment_version()
        self.raise_event(
            AgentDefinitionUpdated(
                agent_id=self.id,
                project_id=self._project_id,
                name=str(self._name.value),
                correlation_id=str(self.id),
            ),
        )

    def activate(self) -> None:
        """Transition from INACTIVE to ACTIVE.

        Raises:
            ConflictError: If not in INACTIVE status.

        """
        if self._status != AgentStatus.INACTIVE:
            raise ConflictError(
                message="Only inactive agents can be activated",
                details={"agent_id": str(self.id), "status": self._status.value},
            )
        self._status = AgentStatus.ACTIVE
        self.touch()
        self.increment_version()
        self.raise_event(
            AgentDefinitionActivated(
                agent_id=self.id,
                project_id=self._project_id,
                correlation_id=str(self.id),
            ),
        )

    def deactivate(self) -> None:
        """Transition from ACTIVE to INACTIVE.

        Raises:
            ConflictError: If not in ACTIVE status.

        """
        if self._status != AgentStatus.ACTIVE:
            raise ConflictError(
                message="Only active agents can be deactivated",
                details={"agent_id": str(self.id), "status": self._status.value},
            )
        self._status = AgentStatus.INACTIVE
        self.touch()
        self.increment_version()
        self.raise_event(
            AgentDefinitionDeactivated(
                agent_id=self.id,
                project_id=self._project_id,
                correlation_id=str(self.id),
            ),
        )

    def mark_error(self) -> None:
        """Transition to ERROR status.

        Can be triggered from ACTIVE state when the agent encounters issues.

        Raises:
            ConflictError: If already archived.

        """
        if self._status == AgentStatus.ARCHIVED:
            raise ConflictError(
                message="Archived agents cannot be marked as error",
                details={"agent_id": str(self.id)},
            )
        self._status = AgentStatus.ERROR
        self.touch()
        self.increment_version()

    def archive(self) -> None:
        """Archive this agent definition.

        Transitions from any non-archived state to ARCHIVED.

        Raises:
            ConflictError: If already archived.

        """
        if self._status == AgentStatus.ARCHIVED:
            raise ConflictError(
                message="Agent is already archived",
                details={"agent_id": str(self.id)},
            )
        self._status = AgentStatus.ARCHIVED
        self.touch()
        self.increment_version()
        self.raise_event(
            AgentDefinitionArchived(
                agent_id=self.id,
                project_id=self._project_id,
                correlation_id=str(self.id),
            ),
        )

    def delete(self) -> None:
        """Mark agent for deletion.

        Raises a domain event. The repository handles actual deletion.

        Raises:
            ConflictError: If already archived.

        """
        if self._status == AgentStatus.ARCHIVED:
            raise ConflictError(
                message="Archived agents cannot be deleted",
                details={"agent_id": str(self.id)},
            )
        self.raise_event(
            AgentDefinitionDeleted(
                agent_id=self.id,
                project_id=self._project_id,
                correlation_id=str(self.id),
            ),
        )

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        name: AgentName,
        description: AgentDescription | None = None,
        agent_type: AgentType,
        model: str,
        provider: str,
        capabilities: tuple[str, ...] = (),
        config: dict[str, Any] | None = None,
        endpoint: AgentEndpoint | None = None,
        created_by: str | None = None,
    ) -> AgentDefinition:
        """Factory method to create a new agent definition.

        Validates invariants and raises AgentDefinitionCreated event.

        Args:
            project_id: The project identifier.
            name: Validated agent name.
            description: Optional description.
            agent_type: The type of agent.
            model: Model identifier string.
            provider: Provider identifier string.
            capabilities: Tuple of capability tags.
            config: Optional model configuration.
            endpoint: Optional custom endpoint URL.
            created_by: Optional creator identifier.

        Returns:
            A new AgentDefinition in ACTIVE status.

        Raises:
            ValidationError: If required fields are missing.

        """
        if not model:
            raise ValidationError(message="Model is required", field="model")
        if not provider:
            raise ValidationError(message="Provider is required", field="provider")
        agent = cls(
            project_id=project_id,
            name=name,
            description=description,
            agent_type=agent_type,
            model=model,
            provider=provider,
            capabilities=capabilities,
            config=config,
            endpoint=endpoint,
            status=AgentStatus.ACTIVE,
            created_by=created_by,
        )
        agent.raise_event(
            AgentDefinitionCreated(
                agent_id=agent.id,
                project_id=project_id,
                name=str(name.value),
                correlation_id=str(agent.id),
            ),
        )
        return agent
