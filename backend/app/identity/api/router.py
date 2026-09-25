"""Identity REST endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query
from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db_session,
    get_redis_client,
)
from app.identity.schemas.responses import (
    ChangePasswordRequest,
    LoginRequest,
    OAuthCallbackRequest,
    RefreshRequest,
    RegisterRequest,
    RequestPasswordResetRequest,
    RequestVerificationRequest,
    ResetPasswordRequest,
    TokenPairResponse,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.identity.services.auth_service import AuthService
from app.infrastructure.database.repositories.identity_repository import (
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyUserRepository,
)
from app.kernel.exceptions.errors import BaseError

if TYPE_CHECKING:
    from app.identity.domain.entities import User

identity_router = APIRouter(prefix="/auth", tags=["auth"])


def _get_auth_service(session: AsyncSession) -> AuthService:
    user_repo = SqlAlchemyUserRepository(session)
    refresh_repo = SqlAlchemyRefreshTokenRepository(session)
    return AuthService(user_repo, refresh_repo)


async def _resolve_org_id(session: AsyncSession, user_id: str) -> str | None:
    """Find the user's first active organization membership, if any."""
    from app.infrastructure.database.repositories.tenant_repository import (
        SqlAlchemyMembershipRepository,
    )

    membership_repo = SqlAlchemyMembershipRepository(session)
    memberships = await membership_repo.list_by_user(user_id)
    for m in memberships:
        if m.is_active:
            return m.organization_id
    return None


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        status=user.status.value,
        email_verified_at=user.email_verified_at.isoformat() if user.email_verified_at else None,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        login_count=user.login_count,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
    )


@identity_router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Register a new user account."""
    service = _get_auth_service(session)
    try:
        user = await service.register(
            email=body.email,
            display_name=body.display_name,
            password=body.password,
        )
        org_id = await _resolve_org_id(session, str(user.id))
        access_token = service.create_access_token(user, org_id=org_id)
        raw_refresh, refresh_entity = service.create_refresh_token(user)
        from app.infrastructure.database.repositories.identity_repository import (
            SqlAlchemyRefreshTokenRepository,
        )

        refresh_repo = SqlAlchemyRefreshTokenRepository(session)
        await refresh_repo.save(refresh_entity)
        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=3600,
        )
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@identity_router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Authenticate with email and password."""
    service = _get_auth_service(session)
    try:
        user = await service.authenticate(email=body.email, password=body.password)
        org_id = await _resolve_org_id(session, str(user.id))
        access_token = service.create_access_token(user, org_id=org_id)
        raw_refresh, refresh_entity = service.create_refresh_token(user)
        from app.infrastructure.database.repositories.identity_repository import (
            SqlAlchemyRefreshTokenRepository,
        )

        refresh_repo = SqlAlchemyRefreshTokenRepository(session)
        await refresh_repo.save(refresh_entity)
        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=3600,
        )
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@identity_router.post("/refresh", response_model=TokenPairResponse)
async def refresh_tokens(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenPairResponse:
    """Refresh access and refresh tokens."""
    service = _get_auth_service(session)
    try:
        new_access, new_refresh, user = await service.refresh_tokens(body.refresh_token)
        org_id = await _resolve_org_id(session, str(user.id))
        # Re-create access token with org_id (refresh_tokens creates one without it)
        new_access = service.create_access_token(user, org_id=org_id)
        return TokenPairResponse(
            access_token=new_access,
            refresh_token=new_refresh.token_hash,
            expires_in=3600,
            user=_user_to_response(user),
        )
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@identity_router.post("/logout", status_code=204)
async def logout(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Logout and revoke all refresh tokens."""
    service = _get_auth_service(session)
    await service.logout_all(current_user.user_id)


@identity_router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """Get the current authenticated user's profile."""
    from app.identity.contracts.repositories import UserRepository
    from app.infrastructure.database.repositories.identity_repository import (
        SqlAlchemyUserRepository,
    )
    from app.kernel.entities.base import UUIDv7

    user_repo: UserRepository = SqlAlchemyUserRepository(session)
    user = await user_repo.find_by_id(UUIDv7.from_string(current_user.user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_response(user)


@identity_router.patch("/me/password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Change the current user's password."""
    from app.identity.contracts.repositories import UserRepository
    from app.infrastructure.database.repositories.identity_repository import (
        SqlAlchemyUserRepository,
    )
    from app.kernel.entities.base import UUIDv7

    service = _get_auth_service(session)
    user_repo: UserRepository = SqlAlchemyUserRepository(session)
    user = await user_repo.find_by_id(UUIDv7.from_string(current_user.user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        await service.change_password(
            user=user,
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


# ─── OAuth Endpoints ─────────────────────────────────────────────

_OAUTH_STATE_TTL_SECONDS = 600  # 10 minutes


@identity_router.get("/oauth/github/authorize")
async def github_authorize(
    state: str = Query(...),
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> dict[str, str]:
    """Get GitHub OAuth authorize URL.

    Stores the state parameter server-side for CSRF validation on callback.
    """
    from app.identity.services.oauth_service import OAuthService

    user_repo = SqlAlchemyUserRepository(session=None)  # type: ignore[arg-type]
    refresh_repo = SqlAlchemyRefreshTokenRepository(session=None)  # type: ignore[arg-type]
    auth_svc = AuthService(user_repo, refresh_repo)
    svc = OAuthService(user_repo, refresh_repo, auth_svc)
    url = svc.get_github_authorize_url(state)
    await redis_client.setex(f"oauth:state:{state}", _OAUTH_STATE_TTL_SECONDS, "1")
    return {"authorize_url": url, "state": state}


@identity_router.get("/oauth/google/authorize")
async def google_authorize(
    state: str = Query(...),
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> dict[str, str]:
    """Get Google OAuth authorize URL.

    Stores the state parameter server-side for CSRF validation on callback.
    """
    from app.identity.services.oauth_service import OAuthService

    user_repo = SqlAlchemyUserRepository(session=None)  # type: ignore[arg-type]
    refresh_repo = SqlAlchemyRefreshTokenRepository(session=None)  # type: ignore[arg-type]
    auth_svc = AuthService(user_repo, refresh_repo)
    svc = OAuthService(user_repo, refresh_repo, auth_svc)
    url = svc.get_google_authorize_url(state)
    await redis_client.setex(f"oauth:state:{state}", _OAUTH_STATE_TTL_SECONDS, "1")
    return {"authorize_url": url, "state": state}


@identity_router.post("/oauth/github/callback", response_model=TokenResponse)
async def github_callback(
    body: OAuthCallbackRequest,
    session: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> TokenResponse:
    """Handle GitHub OAuth callback.

    Validates the OAuth state parameter against the server-side store
    to prevent CSRF attacks. State is single-use and expires after 10 minutes.
    """
    from fastapi import HTTPException as _HTTPException

    from app.identity.services.oauth_service import OAuthService

    state_key = f"oauth:state:{body.state}"
    stored = await redis_client.get(state_key)
    if not stored:
        raise _HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    await redis_client.delete(state_key)

    user_repo = SqlAlchemyUserRepository(session)
    refresh_repo = SqlAlchemyRefreshTokenRepository(session)
    auth_svc = AuthService(user_repo, refresh_repo)
    svc = OAuthService(user_repo, refresh_repo, auth_svc)
    try:
        _user, access_token, raw_refresh = await svc.handle_github_callback(
            code=body.code,
            state=body.state,
        )
        org_id = await _resolve_org_id(session, str(_user.id))
        access_token = auth_svc.create_access_token(_user, org_id=org_id)
        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=3600,
        )
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@identity_router.post("/oauth/google/callback", response_model=TokenResponse)
async def google_callback(
    body: OAuthCallbackRequest,
    session: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> TokenResponse:
    """Handle Google OAuth callback.

    Validates the OAuth state parameter against the server-side store
    to prevent CSRF attacks. State is single-use and expires after 10 minutes.
    """
    from fastapi import HTTPException as _HTTPException

    from app.identity.services.oauth_service import OAuthService

    state_key = f"oauth:state:{body.state}"
    stored = await redis_client.get(state_key)
    if not stored:
        raise _HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    await redis_client.delete(state_key)

    user_repo = SqlAlchemyUserRepository(session)
    refresh_repo = SqlAlchemyRefreshTokenRepository(session)
    auth_svc = AuthService(user_repo, refresh_repo)
    svc = OAuthService(user_repo, refresh_repo, auth_svc)
    try:
        _user, access_token, raw_refresh = await svc.handle_google_callback(
            code=body.code,
            state=body.state,
        )
        org_id = await _resolve_org_id(session, str(_user.id))
        access_token = auth_svc.create_access_token(_user, org_id=org_id)
        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=3600,
        )
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


# ─── Email Verification ──────────────────────────────────────────


@identity_router.post("/verify-email/request", status_code=202)
async def request_email_verification(
    body: RequestVerificationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Request an email verification token."""
    from app.identity.services.verification_service import EmailVerificationService

    user_repo = SqlAlchemyUserRepository(session)
    user = await user_repo.find_by_email(body.email)
    if user is None:
        return {"message": "If the email exists, a verification link has been sent"}
    if user.is_email_verified:
        return {"message": "Email is already verified"}
    svc = EmailVerificationService()
    _raw_token = await svc.create_verification_token(session, user)
    return {"message": "If the email exists, a verification link has been sent"}


@identity_router.post("/verify-email/confirm", response_model=UserResponse)
async def confirm_email_verification(
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """Verify email with a token."""
    from app.identity.services.verification_service import EmailVerificationService

    svc = EmailVerificationService()
    try:
        user = await svc.verify_token(session, body.token)
        return _user_to_response(user)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


# ─── Password Reset ──────────────────────────────────────────────


@identity_router.post("/password-reset/request", status_code=202)
async def request_password_reset(
    body: RequestPasswordResetRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Request a password reset token."""
    from app.identity.services.verification_service import PasswordResetService

    user_repo = SqlAlchemyUserRepository(session)
    user = await user_repo.find_by_email(body.email)
    if user is None:
        return {"message": "If the email exists, a password reset link has been sent"}
    svc = PasswordResetService()
    _raw_token = await svc.create_reset_token(session, user)
    return {"message": "If the email exists, a password reset link has been sent"}


@identity_router.post("/password-reset/confirm", status_code=204)
async def confirm_password_reset(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Reset password with a token."""
    from app.identity.services.verification_service import PasswordResetService

    svc = PasswordResetService()
    try:
        await svc.reset_password(session, body.token, body.new_password)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
