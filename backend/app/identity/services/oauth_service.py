"""OAuth service for GitHub and Google login flows."""

from __future__ import annotations

from typing import Any, cast

import httpx

from app.core.config import get_config
from app.identity.contracts.repositories import RefreshTokenRepository, UserRepository
from app.identity.domain.entities import User
from app.identity.domain.enums import OAuthProvider, UserStatus
from app.identity.services.auth_service import AuthService
from app.kernel.exceptions.errors import ConflictError, UnauthorizedError


class OAuthService:
    """Service handling OAuth provider flows."""

    def __init__(
        self,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
        auth_service: AuthService,
    ) -> None:
        self._user_repo = user_repo
        self._refresh_token_repo = refresh_token_repo
        self._auth_service = auth_service
        self._config = get_config()

    def get_github_authorize_url(self, state: str) -> str:
        """Generate GitHub OAuth authorize URL."""
        client_id = self._config.github_client_id
        if not client_id:
            raise ConflictError(message="GitHub OAuth is not configured")
        return (
            f"https://github.com/login/oauth/authorize"
            f"?client_id={client_id}"
            f"&scope=user:email"
            f"&state={state}"
        )

    def get_google_authorize_url(self, state: str) -> str:
        """Generate Google OAuth authorize URL."""
        client_id = self._config.google_client_id
        if not client_id:
            raise ConflictError(message="Google OAuth is not configured")
        return (
            f"https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={client_id}"
            f"&redirect_uri={self._config.oauth_redirect_uri}"
            f"&response_type=code"
            f"&scope=openid email profile"
            f"&state={state}"
        )

    async def handle_github_callback(
        self,
        code: str,
        state: str,
    ) -> tuple[User, str, str]:
        """Exchange GitHub code for tokens, find or create user.

        Returns (user, access_token, refresh_token_raw).
        """
        token_data = await self._exchange_github_code(code)
        access_token = token_data.get("access_token", "")
        if not access_token:
            raise UnauthorizedError(message="Failed to obtain GitHub access token")

        github_user = await self._fetch_github_user(access_token)
        github_id = str(github_user.get("id", ""))
        email = github_user.get("email", "")
        name = github_user.get("name", "") or github_user.get("login", "GitHub User")
        avatar_url = github_user.get("avatar_url")

        if not email:
            emails = await self._fetch_github_emails(access_token)
            for e in emails:
                if e.get("primary"):
                    email = e.get("email", "")
                    break
            if not email and emails:
                email = emails[0].get("email", "")

        if not email:
            raise UnauthorizedError(message="Unable to retrieve email from GitHub")

        user = await self._find_or_create_user(
            provider=OAuthProvider.GITHUB,
            provider_user_id=github_id,
            email=email,
            display_name=name,
            avatar_url=avatar_url,
            oauth_access_token=access_token,
        )

        new_access = self._auth_service.create_access_token(user)
        _raw_refresh, refresh_entity = self._auth_service.create_refresh_token(user)
        await self._refresh_token_repo.save(refresh_entity)
        return user, new_access, _raw_refresh

    async def handle_google_callback(
        self,
        code: str,
        state: str,
    ) -> tuple[User, str, str]:
        """Exchange Google code for tokens, find or create user.

        Returns (user, access_token, refresh_token_raw).
        """
        token_data = await self._exchange_google_code(code)
        access_token = token_data.get("access_token", "")
        if not access_token:
            raise UnauthorizedError(message="Failed to obtain Google access token")

        google_user = await self._fetch_google_user(access_token)
        google_id = google_user.get("sub", "") or google_user.get("id", "")
        email = google_user.get("email", "")
        name = google_user.get("name", "Google User")
        avatar_url = google_user.get("picture")

        if not email or not google_id:
            raise UnauthorizedError(message="Unable to retrieve email from Google")

        user = await self._find_or_create_user(
            provider=OAuthProvider.GOOGLE,
            provider_user_id=google_id,
            email=email,
            display_name=name,
            avatar_url=avatar_url,
            oauth_access_token=access_token,
        )

        new_access = self._auth_service.create_access_token(user)
        _raw_refresh, refresh_entity = self._auth_service.create_refresh_token(user)
        await self._refresh_token_repo.save(refresh_entity)
        return user, new_access, _raw_refresh

    async def _find_or_create_user(
        self,
        *,
        provider: OAuthProvider,
        provider_user_id: str,
        email: str,
        display_name: str,
        avatar_url: str | None,
        oauth_access_token: str,
    ) -> User:
        """Find existing user by OAuth or email, or create new."""
        existing_user = await self._user_repo.find_by_email(email)
        if existing_user is not None:
            if existing_user.status == UserStatus.PENDING_VERIFICATION:
                existing_user.verify_email()
                await self._user_repo.save(existing_user)
            existing_user.record_login()
            await self._user_repo.save(existing_user)
            return existing_user

        user = User.create(
            email=email,
            display_name=display_name,
            password_hash=None,
        )
        user.verify_email()
        if avatar_url:
            user.update_profile(avatar_url=avatar_url)
        user.record_login()
        await self._user_repo.save(user)
        return user

    async def _exchange_github_code(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": self._config.github_client_id,
                    "client_secret": self._config.github_client_secret,
                    "code": code,
                },
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
            resp.raise_for_status()
            return cast("dict[str, Any]", resp.json())

    async def _fetch_github_user(self, access_token: str) -> dict[str, Any]:
        """Fetch authenticated user profile from GitHub."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            return cast("dict[str, Any]", resp.json())

    async def _fetch_github_emails(self, access_token: str) -> list[dict[str, Any]]:
        """Fetch user emails from GitHub."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            return cast("list[dict[str, Any]]", resp.json())

    async def _exchange_google_code(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self._config.google_client_id,
                    "client_secret": self._config.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self._config.oauth_redirect_uri,
                },
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
            resp.raise_for_status()
            return cast("dict[str, Any]", resp.json())

    async def _fetch_google_user(self, access_token: str) -> dict[str, Any]:
        """Fetch authenticated user profile from Google."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            return cast("dict[str, Any]", resp.json())
