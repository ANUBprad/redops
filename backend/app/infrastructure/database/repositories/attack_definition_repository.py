"""SQLAlchemy repository for Attack Definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database.models.attack_definition import AttackDefinitionModel
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError
from app.redteam.contracts.repositories import (
    AttackDefinitionQuery,
    AttackDefinitionRepository,
    PaginatedAttackDefinitions,
)
from app.redteam.domain.entities import AttackDefinition
from app.redteam.domain.enums import AttackCategory, AttackDefinitionStatus, AttackSeverity
from app.redteam.domain.value_objects import AttackTemplate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_SORT_MAP: dict[str, str] = {
    "name": "name",
    "category": "category",
    "severity": "severity",
    "status": "status",
    "created_at": "created_at",
    "updated_at": "updated_at",
}


def _get_sort_column(sort_by: str) -> str:
    return _SORT_MAP.get(sort_by, "created_at")


class SqlAlchemyAttackDefinitionRepository(AttackDefinitionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, definition: AttackDefinition) -> None:
        model = self._to_model(definition)
        try:
            await self._session.merge(model)
        except IntegrityError as exc:
            raise ConflictError(f"Attack definition '{definition.name}' conflicts") from exc

    async def find_by_id(self, definition_id: UUIDv7) -> AttackDefinition | None:
        stmt = select(AttackDefinitionModel).where(AttackDefinitionModel.id == str(definition_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list(self, query: AttackDefinitionQuery) -> PaginatedAttackDefinitions:
        stmt = select(AttackDefinitionModel)

        if query.category:
            stmt = stmt.where(AttackDefinitionModel.category == query.category.value)
        if query.severity:
            stmt = stmt.where(AttackDefinitionModel.severity == query.severity.value)
        if query.status:
            stmt = stmt.where(AttackDefinitionModel.status == query.status.value)
        if query.search:
            like = f"%{query.search}%"
            stmt = stmt.where(
                or_(
                    AttackDefinitionModel.name.ilike(like),
                    AttackDefinitionModel.description.ilike(like),
                )
            )

        sort_col = _get_sort_column(query.sort_by)
        sort_attr = getattr(AttackDefinitionModel, sort_col, AttackDefinitionModel.created_at)
        order = sort_attr.desc() if query.sort_order == "desc" else sort_attr.asc()
        stmt = stmt.order_by(order)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (query.page - 1) * query.page_size
        stmt = stmt.offset(offset).limit(query.page_size)

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return PaginatedAttackDefinitions(
            items=[self._to_domain(m) for m in models],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def delete(self, definition_id: UUIDv7) -> bool:
        stmt = select(AttackDefinitionModel).where(AttackDefinitionModel.id == str(definition_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self._session.delete(model)
        return True

    async def exists(self, definition_id: UUIDv7) -> bool:
        stmt = select(AttackDefinitionModel).where(AttackDefinitionModel.id == str(definition_id))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    @staticmethod
    def _to_model(definition: AttackDefinition) -> AttackDefinitionModel:
        return AttackDefinitionModel(
            id=str(definition.id),
            name=definition.name,
            description=definition.description,
            category=definition.category.value,
            severity=definition.severity.value,
            status=definition.status.value,
            template=_template_to_dict(definition.template),
            parameters=dict(definition.parameters or {}),
            tags=list(definition.tags),
            created_by=definition.created_by,
            version=definition.version,
            created_at=definition.created_at,
            updated_at=definition.updated_at,
        )

    @staticmethod
    def _to_domain(model: AttackDefinitionModel) -> AttackDefinition:
        params: dict[str, Any] = dict(model.parameters) if model.parameters else {}
        tags_tuple: tuple[str, ...] = tuple(model.tags or [])
        return AttackDefinition(
            entity_id=UUIDv7(UUID(model.id)),
            name=model.name,
            description=model.description,
            category=AttackCategory(model.category),
            severity=AttackSeverity(model.severity),
            status=AttackDefinitionStatus(model.status),
            template=_dict_to_template(model.template),
            parameters=params,
            tags=tags_tuple,
            created_by=model.created_by,
        )


def _template_to_dict(template: AttackTemplate | None) -> dict[str, Any]:
    if template is None:
        return {}
    return {
        "name": template.name,
        "description": template.description,
        "category": template.category.value,
        "severity": template.severity.value,
        "prompt_template": template.prompt_template,
        "system_prompt_override": template.system_prompt_override,
        "expected_behavior": template.expected_behavior,
        "parameters": template.parameters,
        "tags": list(template.tags),
    }


def _dict_to_template(data: dict[str, Any] | None) -> AttackTemplate | None:
    if not data:
        return None
    return AttackTemplate(
        name=data.get("name", ""),
        description=data.get("description", ""),
        category=AttackCategory(data.get("category", AttackCategory.PROMPT_INJECTION.value)),
        severity=AttackSeverity(data.get("severity", AttackSeverity.MEDIUM.value)),
        prompt_template=data.get("prompt_template", ""),
        system_prompt_override=data.get("system_prompt_override"),
        expected_behavior=data.get("expected_behavior", ""),
        parameters=dict(data.get("parameters", {})),
        tags=tuple(data.get("tags", [])),
    )
