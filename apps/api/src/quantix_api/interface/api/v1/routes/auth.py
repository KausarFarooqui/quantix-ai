"""Email/password authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status

from quantix_api.application.dto.auth import AuthTokens, LoginInput, RegisterInput
from quantix_api.interface.api.v1.dependencies.auth import ClientIp, CurrentUser
from quantix_api.interface.api.v1.dependencies.use_cases import (
    LoginUseCaseDep,
    LogoutUseCaseDep,
    RefreshUseCaseDep,
    RegisterUseCaseDep,
)
from quantix_api.interface.api.v1.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_token_response(tokens: AuthTokens) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tenant workspace and its owner user",
)
async def register(
    body: RegisterRequest, use_case: RegisterUseCaseDep, ip_address: ClientIp
) -> TokenResponse:
    result = await use_case.execute(
        RegisterInput(
            organization_name=body.organization_name,
            email=body.email,
            password=body.password.get_secret_value(),
            full_name=body.full_name,
            ip_address=ip_address,
        )
    )
    return _to_token_response(result.tokens)


@router.post("/login", response_model=TokenResponse, summary="Log in with email + password")
async def login(body: LoginRequest, use_case: LoginUseCaseDep, ip_address: ClientIp) -> TokenResponse:
    result = await use_case.execute(
        LoginInput(
            tenant_slug=body.tenant_slug,
            email=body.email,
            password=body.password.get_secret_value(),
            ip_address=ip_address,
        )
    )
    return _to_token_response(result.tokens)


@router.post("/refresh", response_model=TokenResponse, summary="Exchange a refresh token for a new pair")
async def refresh(
    body: RefreshRequest, use_case: RefreshUseCaseDep, ip_address: ClientIp
) -> TokenResponse:
    result = await use_case.execute(body.refresh_token, ip_address=ip_address)
    return _to_token_response(result.tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke a refresh token")
async def logout(
    body: LogoutRequest,
    use_case: LogoutUseCaseDep,
    current_user: CurrentUser,
    ip_address: ClientIp,
) -> None:
    await use_case.execute(
        body.refresh_token,
        actor_user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        ip_address=ip_address,
    )


@router.get("/me", response_model=UserPublic, summary="Get the currently authenticated user")
async def read_current_user(current_user: CurrentUser) -> UserPublic:
    return UserPublic(
        id=current_user.id,
        tenant_id=current_user.tenant_id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        is_active=current_user.is_active,
        is_email_verified=current_user.is_email_verified,
    )
