"""Data transfer objects for the auth use cases.

Plain, frozen dataclasses — not Pydantic models. The interface layer's
Pydantic schemas map onto these at the boundary; use cases never see a
FastAPI/Pydantic type, keeping ``application/`` framework-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RegisterInput:
    organization_name: str
    email: str
    password: str
    full_name: str
    ip_address: str | None = None


@dataclass(frozen=True, slots=True)
class LoginInput:
    tenant_slug: str
    email: str
    password: str
    ip_address: str | None = None


@dataclass(frozen=True, slots=True)
class OAuthCallbackInput:
    provider: str
    code: str
    state: str
    redirect_uri: str
    ip_address: str | None = None


@dataclass(frozen=True, slots=True)
class AuthTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


@dataclass(frozen=True, slots=True)
class AuthResult:
    tokens: AuthTokens
    user_id: UUID
    tenant_id: UUID
    is_new_account: bool = False
