"""Pydantic request/response schemas for authentication endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class RegisterRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=256)
    full_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    tenant_slug: str = Field(min_length=1, max_length=63)
    email: EmailStr
    password: SecretStr


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserPublic(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: UUID
    tenant_id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    is_email_verified: bool


class OAuthAuthorizeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    authorization_url: str
