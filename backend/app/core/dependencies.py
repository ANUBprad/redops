"""FastAPI dependency injection for shared resources."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, Request
from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from temporalio.client import Client as TemporalClient

from app.core.config import AppConfig, get_config


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Authenticated user identity."""

    user_id: str
    email: str = ""
    name: str = ""
    roles: tuple[str, ...] = ()
    org_id: str | None = None


async def get_current_user(request: Request) -> CurrentUser:
    """Extract and validate the authenticated user from the JWT token.

    Decodes the JWT access token from the Authorization header.
    Always requires a valid token — no anonymous fallback.
    """
    config = get_config()
    from fastapi import HTTPException

    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer ") or not auth_header[7:]:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    token = auth_header[7:]
    try:
        payload = jwt.decode(
            token,
            config.app_secret_key,
            algorithms=[config.jwt_algorithm],
        )
        user_id = payload.get("sub", "")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing subject")
        return CurrentUser(
            user_id=user_id,
            email=payload.get("email", ""),
            name=payload.get("name", ""),
            roles=tuple(payload.get("roles", [])),
            org_id=payload.get("org_id"),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from None


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, Any]:
    """Provide an async database session for the request lifecycle."""
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_config_dependency() -> AppConfig:
    """Return the application configuration singleton."""
    return get_config()


def get_redis_client(request: Request) -> aioredis.Redis:
    """Return the application Redis client from app state."""
    client: aioredis.Redis = request.app.state.redis_client
    return client


def get_temporal_client(request: Request) -> TemporalClient:
    """Return the application Temporal client from app state."""
    client: TemporalClient = request.app.state.temporal_client
    return client


async def _assert_membership(
    *,
    user_id: str,
    org_id: str,
    session: AsyncSession,
) -> None:
    """Raise 403 unless ``user_id`` is an active member of ``org_id``."""
    from fastapi import HTTPException

    from app.infrastructure.database.repositories.tenant_repository import (
        SqlAlchemyMembershipRepository,
        SqlAlchemyOrganizationRepository,
    )
    from app.kernel.exceptions.errors import UnauthorizedError
    from app.tenant.services.tenant_service import OrganizationService

    service = OrganizationService(
        SqlAlchemyOrganizationRepository(session),
        SqlAlchemyMembershipRepository(session),
    )
    try:
        await service.check_membership(user_id, org_id)
    except UnauthorizedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


async def require_org_membership(
    org_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Require that the current user is an active member of ``org_id``.

    Single shared authorization choke point for org-scoped resource reads
    (audit logs, notifications, …). Route handlers declare this as a
    ``Depends`` and FastAPI resolves ``org_id`` from the path automatically,
    so every org-scoped endpoint funnels through the same membership
    assertion defined here.
    """
    await _assert_membership(
        user_id=current_user.user_id,
        org_id=org_id,
        session=session,
    )


async def require_current_org_membership(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> str:
    """Require the current user to be an active member of their JWT org.

    Returns the caller's org id for resources without an ``{org_id}`` path
    segment. Used to tenant-scope create/list/by-id operations on resources
    that carry their tenant as ``project_id``/``organization_id``.
    """
    from fastapi import HTTPException

    if not current_user.org_id:
        raise HTTPException(status_code=403, detail="No organization context")
    await _assert_membership(
        user_id=current_user.user_id,
        org_id=current_user.org_id,
        session=session,
    )
    return current_user.org_id


async def require_owned_evaluation(
    evaluation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Require the evaluation to belong to the caller's organization.

    Loads the evaluation and asserts its ``project_id`` equals the caller's
    JWT org, after revalidating membership. Denies cross-tenant access by
    brute-forcing object ids.
    """
    from fastapi import HTTPException

    from app.infrastructure.database.repositories.evaluation_repository import (
        SqlAlchemyEvaluationRepository,
    )
    from app.kernel.entities.base import UUIDv7

    if not current_user.org_id:
        raise HTTPException(status_code=403, detail="No organization context")
    await _assert_membership(
        user_id=current_user.user_id,
        org_id=current_user.org_id,
        session=session,
    )

    evaluation = await SqlAlchemyEvaluationRepository(session).get_by_id(
        UUIDv7.from_string(evaluation_id),
    )
    if evaluation is None:
        raise HTTPException(status_code=404, detail=f"Evaluation not found: {evaluation_id}")
    if evaluation.project_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")


async def require_owned_run(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Require the run to belong to the caller's organization.

    Resolves the run, obtains its parent ``evaluation_id``, and delegates
    to :func:`require_owned_evaluation` so every run-keyed raw LLM-I/O
    surface funnels through the single existing tenant/ownership choke
    point. Runs without a parent evaluation fall back to the run's
    persisted ``metadata.project_id``. Unknown or malformed ids stay
    truthful with 404; cross-tenant access gets 403.
    """
    from fastapi import HTTPException

    from app.infrastructure.database.repositories.evaluation_run_repository import (
        SqlAlchemyEvaluationRunRepository,
    )
    from app.kernel.entities.base import UUIDv7

    try:
        r_id = UUIDv7.from_string(run_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Evaluation run not found: {run_id}") from None

    run = await SqlAlchemyEvaluationRunRepository(session).find_by_id(r_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Evaluation run not found: {run_id}")
    if run.evaluation_id:
        await require_owned_evaluation(run.evaluation_id, current_user, session)
        return

    if not current_user.org_id:
        raise HTTPException(status_code=403, detail="No organization context")
    await _assert_membership(
        user_id=current_user.user_id,
        org_id=current_user.org_id,
        session=session,
    )
    project_id = run.metadata.project_id if run.metadata is not None else None
    if project_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")


async def require_owned_experiment(
    experiment_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Require the experiment to belong to the caller's organization.

    Loads the experiment and asserts its ``project_id`` equals the
    caller's JWT org, after revalidating membership. Unknown or malformed
    ids stay truthful with 404; cross-tenant access gets 403.
    """
    from fastapi import HTTPException

    from app.infrastructure.database.repositories.experiment_repository import (
        SqlAlchemyExperimentRepository,
    )
    from app.kernel.entities.base import UUIDv7

    if not current_user.org_id:
        raise HTTPException(status_code=403, detail="No organization context")
    await _assert_membership(
        user_id=current_user.user_id,
        org_id=current_user.org_id,
        session=session,
    )

    try:
        exp_id = UUIDv7.from_string(experiment_id)
    except ValueError:
        raise HTTPException(
            status_code=404, detail=f"Experiment not found: {experiment_id}"
        ) from None
    experiment = await SqlAlchemyExperimentRepository(session).find_by_id(exp_id)
    if experiment is None:
        raise HTTPException(
            status_code=404, detail=f"Experiment not found: {experiment_id}"
        )
    if experiment.project_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")
