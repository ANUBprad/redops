"""Pydantic schemas for Identity API."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    display_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Request body for email/password login."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Request body for password change."""

    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    """Response for a user."""

    id: str
    email: str
    display_name: str
    avatar_url: str | None = None
    status: str
    email_verified_at: str | None = None
    last_login_at: str | None = None
    login_count: int = 0
    created_at: str
    updated_at: str


class TokenResponse(BaseModel):
    """Response containing access and refresh tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPairResponse(BaseModel):
    """Response for token refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class OAuthCallbackRequest(BaseModel):
    """Request body for OAuth callback."""

    code: str
    state: str = ""


class RequestVerificationRequest(BaseModel):
    """Request body for email verification request."""

    email: EmailStr


class VerifyEmailRequest(BaseModel):
    """Request body for email verification confirm."""

    token: str


class RequestPasswordResetRequest(BaseModel):
    """Request body for password reset request."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request body for password reset confirm."""

    token: str
    new_password: str = Field(min_length=8, max_length=128)
