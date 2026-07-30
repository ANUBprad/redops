"""Commands and queries for the Red Team domain."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.redteam.domain.enums import AttackCategory, AttackSeverity


@dataclass(frozen=True, slots=True)
class CreateAttackDefinitionCommand:
    name: str
    description: str = ""
    category: str = AttackCategory.PROMPT_INJECTION.value
    severity: str = AttackSeverity.MEDIUM.value
    prompt_template: str = ""
    system_prompt_override: str | None = None
    expected_behavior: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    created_by: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateAttackDefinitionCommand:
    definition_id: str
    name: str | None = None
    description: str | None = None
    category: str | None = None
    severity: str | None = None
    prompt_template: str | None = None
    system_prompt_override: str | None = None
    expected_behavior: str | None = None
    parameters: dict[str, Any] | None = None
    tags: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class ActivateAttackDefinitionCommand:
    definition_id: str


@dataclass(frozen=True, slots=True)
class ArchiveAttackDefinitionCommand:
    definition_id: str


@dataclass(frozen=True, slots=True)
class DeleteAttackDefinitionCommand:
    definition_id: str


@dataclass(frozen=True, slots=True)
class GetAttackDefinitionQuery:
    definition_id: str


@dataclass(frozen=True, slots=True)
class ListAttackDefinitionsQuery:
    category: str | None = None
    severity: str | None = None
    status: str | None = None
    search: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True, slots=True)
class CreateAttackRunCommand:
    evaluation_run_id: str | None = None
    attack_definition_ids: tuple[str, ...] = ()
    configuration: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StartAttackRunCommand:
    run_id: str
    total_items: int = 0


@dataclass(frozen=True, slots=True)
class CompleteAttackRunCommand:
    run_id: str


@dataclass(frozen=True, slots=True)
class FailAttackRunCommand:
    run_id: str
    error_message: str = ""


@dataclass(frozen=True, slots=True)
class CancelAttackRunCommand:
    run_id: str


@dataclass(frozen=True, slots=True)
class GetAttackRunQuery:
    run_id: str


@dataclass(frozen=True, slots=True)
class ListAttackRunsQuery:
    status: str | None = None
    evaluation_run_id: str | None = None
    category: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20
