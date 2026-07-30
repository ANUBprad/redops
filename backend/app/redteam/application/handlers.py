"""CQRS handlers for the Red Team domain."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import NotFoundError
from app.redteam.application.commands import (
    ActivateAttackDefinitionCommand,
    ArchiveAttackDefinitionCommand,
    CancelAttackRunCommand,
    CompleteAttackRunCommand,
    CreateAttackDefinitionCommand,
    CreateAttackRunCommand,
    DeleteAttackDefinitionCommand,
    FailAttackRunCommand,
    GetAttackDefinitionQuery,
    GetAttackRunQuery,
    ListAttackDefinitionsQuery,
    ListAttackRunsQuery,
    StartAttackRunCommand,
    UpdateAttackDefinitionCommand,
)
from app.redteam.contracts.repositories import (
    AttackDefinitionQuery,
    AttackDefinitionRepository,
    AttackRunQuery,
    AttackRunRepository,
)
from app.redteam.domain.entities import AttackDefinition, AttackRun
from app.redteam.domain.enums import (
    AttackCategory,
    AttackDefinitionStatus,
    AttackSeverity,
    AttackStatus,
)
from app.redteam.domain.value_objects import AttackConfiguration, AttackTemplate

if TYPE_CHECKING:
    from app.redteam.contracts.repositories import PaginatedAttackDefinitions, PaginatedAttackRuns


class CreateAttackDefinitionHandler:
    def __init__(self, repository: AttackDefinitionRepository) -> None:
        self._repository = repository

    async def handle(self, command: CreateAttackDefinitionCommand) -> AttackDefinition:
        template = AttackTemplate(
            name=command.name,
            description=command.description,
            category=AttackCategory(command.category),
            severity=AttackSeverity(command.severity),
            prompt_template=command.prompt_template,
            system_prompt_override=command.system_prompt_override,
            expected_behavior=command.expected_behavior,
        )
        definition = AttackDefinition.create(
            name=command.name,
            description=command.description,
            category=AttackCategory(command.category),
            severity=AttackSeverity(command.severity),
            template=template,
            parameters=dict(command.parameters),
            tags=tuple(command.tags),
            created_by=command.created_by,
        )
        await self._repository.save(definition)
        return definition


class UpdateAttackDefinitionHandler:
    def __init__(self, repository: AttackDefinitionRepository) -> None:
        self._repository = repository

    async def handle(self, command: UpdateAttackDefinitionCommand) -> AttackDefinition:
        def_id = UUIDv7.from_string(command.definition_id)
        definition = await self._repository.find_by_id(def_id)
        if definition is None:
            raise NotFoundError(f"Attack definition {command.definition_id} not found")

        template_kwargs: dict[str, Any] = {}
        if command.prompt_template is not None:
            template_kwargs["prompt_template"] = command.prompt_template
        if command.system_prompt_override is not None:
            template_kwargs["system_prompt_override"] = command.system_prompt_override
        if command.expected_behavior is not None:
            template_kwargs["expected_behavior"] = command.expected_behavior
        if template_kwargs:
            template = AttackTemplate(
                name=definition.name,
                description=definition.description,
                category=definition.category,
                severity=definition.severity,
                prompt_template=template_kwargs.get("prompt_template", definition.template.prompt_template),
                system_prompt_override=template_kwargs.get("system_prompt_override", definition.template.system_prompt_override),
                expected_behavior=template_kwargs.get("expected_behavior", definition.template.expected_behavior),
            )
        else:
            template = None

        definition.update(
            name=command.name,
            description=command.description,
            category=AttackCategory(command.category) if command.category else None,
            severity=AttackSeverity(command.severity) if command.severity else None,
            template=template,
            parameters=dict(command.parameters) if command.parameters is not None else None,
            tags=tuple(command.tags) if command.tags is not None else None,
        )
        await self._repository.save(definition)
        return definition


class ActivateAttackDefinitionHandler:
    def __init__(self, repository: AttackDefinitionRepository) -> None:
        self._repository = repository

    async def handle(self, command: ActivateAttackDefinitionCommand) -> AttackDefinition:
        def_id = UUIDv7.from_string(command.definition_id)
        definition = await self._repository.find_by_id(def_id)
        if definition is None:
            raise NotFoundError(f"Attack definition {command.definition_id} not found")
        definition.activate()
        await self._repository.save(definition)
        return definition


class ArchiveAttackDefinitionHandler:
    def __init__(self, repository: AttackDefinitionRepository) -> None:
        self._repository = repository

    async def handle(self, command: ArchiveAttackDefinitionCommand) -> AttackDefinition:
        def_id = UUIDv7.from_string(command.definition_id)
        definition = await self._repository.find_by_id(def_id)
        if definition is None:
            raise NotFoundError(f"Attack definition {command.definition_id} not found")
        definition.archive()
        await self._repository.save(definition)
        return definition


class DeleteAttackDefinitionHandler:
    def __init__(self, repository: AttackDefinitionRepository) -> None:
        self._repository = repository

    async def handle(self, command: DeleteAttackDefinitionCommand) -> None:
        def_id = UUIDv7.from_string(command.definition_id)
        deleted = await self._repository.delete(def_id)
        if not deleted:
            raise NotFoundError(f"Attack definition {command.definition_id} not found")


class GetAttackDefinitionHandler:
    def __init__(self, repository: AttackDefinitionRepository) -> None:
        self._repository = repository

    async def handle(self, query: GetAttackDefinitionQuery) -> AttackDefinition:
        def_id = UUIDv7.from_string(query.definition_id)
        definition = await self._repository.find_by_id(def_id)
        if definition is None:
            raise NotFoundError(f"Attack definition {query.definition_id} not found")
        return definition


class ListAttackDefinitionsHandler:
    def __init__(self, repository: AttackDefinitionRepository) -> None:
        self._repository = repository

    async def handle(self, query: ListAttackDefinitionsQuery) -> PaginatedAttackDefinitions:
        domain_query = AttackDefinitionQuery(
            category=AttackCategory(query.category) if query.category else None,
            severity=AttackSeverity(query.severity) if query.severity else None,
            status=AttackDefinitionStatus(query.status) if query.status else None,
            search=query.search,
            sort_by=query.sort_by,
            sort_order=query.sort_order,
            page=query.page,
            page_size=query.page_size,
        )
        return await self._repository.list(domain_query)


class CreateAttackRunHandler:
    def __init__(self, repository: AttackRunRepository) -> None:
        self._repository = repository

    async def handle(self, command: CreateAttackRunCommand) -> AttackRun:
        def_ids = tuple(
            UUIDv7.from_string(did) for did in command.attack_definition_ids
        )
        config = _dict_to_config(command.configuration) if command.configuration else None
        run = AttackRun.create(
            evaluation_run_id=UUIDv7.from_string(command.evaluation_run_id) if command.evaluation_run_id else None,
            attack_definition_ids=def_ids,
            configuration=config,
        )
        await self._repository.save(run)
        return run


class StartAttackRunHandler:
    def __init__(self, repository: AttackRunRepository) -> None:
        self._repository = repository

    async def handle(self, command: StartAttackRunCommand) -> AttackRun:
        run_id = UUIDv7.from_string(command.run_id)
        run = await self._repository.find_by_id(run_id)
        if run is None:
            raise NotFoundError(f"Attack run {command.run_id} not found")
        run.start(total_items=command.total_items)
        await self._repository.save(run)
        return run


class CompleteAttackRunHandler:
    def __init__(self, repository: AttackRunRepository) -> None:
        self._repository = repository

    async def handle(self, command: CompleteAttackRunCommand) -> AttackRun:
        run_id = UUIDv7.from_string(command.run_id)
        run = await self._repository.find_by_id(run_id)
        if run is None:
            raise NotFoundError(f"Attack run {command.run_id} not found")
        run.complete()
        await self._repository.save(run)
        return run


class FailAttackRunHandler:
    def __init__(self, repository: AttackRunRepository) -> None:
        self._repository = repository

    async def handle(self, command: FailAttackRunCommand) -> AttackRun:
        run_id = UUIDv7.from_string(command.run_id)
        run = await self._repository.find_by_id(run_id)
        if run is None:
            raise NotFoundError(f"Attack run {command.run_id} not found")
        run.fail(error_message=command.error_message)
        await self._repository.save(run)
        return run


class CancelAttackRunHandler:
    def __init__(self, repository: AttackRunRepository) -> None:
        self._repository = repository

    async def handle(self, command: CancelAttackRunCommand) -> AttackRun:
        run_id = UUIDv7.from_string(command.run_id)
        run = await self._repository.find_by_id(run_id)
        if run is None:
            raise NotFoundError(f"Attack run {command.run_id} not found")
        run.cancel()
        await self._repository.save(run)
        return run


class GetAttackRunHandler:
    def __init__(self, repository: AttackRunRepository) -> None:
        self._repository = repository

    async def handle(self, query: GetAttackRunQuery) -> AttackRun:
        run_id = UUIDv7.from_string(query.run_id)
        run = await self._repository.find_by_id(run_id)
        if run is None:
            raise NotFoundError(f"Attack run {query.run_id} not found")
        return run


class ListAttackRunsHandler:
    def __init__(self, repository: AttackRunRepository) -> None:
        self._repository = repository

    async def handle(self, query: ListAttackRunsQuery) -> PaginatedAttackRuns:
        domain_query = AttackRunQuery(
            status=AttackStatus(query.status) if query.status else None,
            evaluation_run_id=query.evaluation_run_id,
            category=AttackCategory(query.category) if query.category else None,
            sort_by=query.sort_by,
            sort_order=query.sort_order,
            page=query.page,
            page_size=query.page_size,
        )
        return await self._repository.list(domain_query)


def _dict_to_config(data: dict[str, Any] | None) -> AttackConfiguration | None:
    if not data:
        return None
    return AttackConfiguration(
        target_provider=data.get("target_provider", ""),
        target_model=data.get("target_model", ""),
        temperature=data.get("temperature", 0.0),
        max_tokens=data.get("max_tokens", 2048),
        timeout_seconds=data.get("timeout_seconds", 60),
        system_prompt=data.get("system_prompt", ""),
        attack_definitions=tuple(UUIDv7.from_string(aid) for aid in data.get("attack_definitions", [])),
        categories=tuple(AttackCategory(c) for c in data.get("categories", [])),
        severities=tuple(AttackSeverity(s) for s in data.get("severities", [])),
        max_scenarios=data.get("max_scenarios", 0),
        continue_on_violation=data.get("continue_on_violation", True),
        metadata=dict(data.get("metadata", {})),
    )
