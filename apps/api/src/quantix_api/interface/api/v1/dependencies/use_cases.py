"""FastAPI providers assembling use cases from repositories + services.

This is the last stop in the DI chain before a route handler: everything
here is request-scoped (built fresh per request from request-scoped
repositories), which is correct for use cases since they hold no state
between calls.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from quantix_api.application.use_cases.login_user import LoginUserUseCase
from quantix_api.application.use_cases.logout_user import LogoutUserUseCase
from quantix_api.application.use_cases.oauth_login import OAuthLoginUseCase
from quantix_api.application.use_cases.refresh_access_token import RefreshAccessTokenUseCase
from quantix_api.application.use_cases.register_user import RegisterUserUseCase
from quantix_api.interface.api.v1.dependencies.repositories import (
    OAuthAccountRepo,
    RefreshTokenRepo,
    TenantRepo,
    UserRepo,
)
from quantix_api.interface.api.v1.dependencies.services import (
    AuditLoggerDep,
    PasswordHasherDep,
    TokenServiceDep,
)


def get_register_use_case(
    tenant_repo: TenantRepo,
    user_repo: UserRepo,
    refresh_token_repo: RefreshTokenRepo,
    password_hasher: PasswordHasherDep,
    token_service: TokenServiceDep,
    audit_logger: AuditLoggerDep,
) -> RegisterUserUseCase:
    return RegisterUserUseCase(
        tenant_repo=tenant_repo,
        user_repo=user_repo,
        refresh_token_repo=refresh_token_repo,
        password_hasher=password_hasher,
        token_service=token_service,
        audit_logger=audit_logger,
    )


def get_login_use_case(
    tenant_repo: TenantRepo,
    user_repo: UserRepo,
    refresh_token_repo: RefreshTokenRepo,
    password_hasher: PasswordHasherDep,
    token_service: TokenServiceDep,
    audit_logger: AuditLoggerDep,
) -> LoginUserUseCase:
    return LoginUserUseCase(
        tenant_repo=tenant_repo,
        user_repo=user_repo,
        refresh_token_repo=refresh_token_repo,
        password_hasher=password_hasher,
        token_service=token_service,
        audit_logger=audit_logger,
    )


def get_refresh_use_case(
    refresh_token_repo: RefreshTokenRepo,
    user_repo: UserRepo,
    token_service: TokenServiceDep,
    audit_logger: AuditLoggerDep,
) -> RefreshAccessTokenUseCase:
    return RefreshAccessTokenUseCase(
        refresh_token_repo=refresh_token_repo,
        user_repo=user_repo,
        token_service=token_service,
        audit_logger=audit_logger,
    )


def get_logout_use_case(
    refresh_token_repo: RefreshTokenRepo,
    token_service: TokenServiceDep,
    audit_logger: AuditLoggerDep,
) -> LogoutUserUseCase:
    return LogoutUserUseCase(
        refresh_token_repo=refresh_token_repo,
        token_service=token_service,
        audit_logger=audit_logger,
    )


def get_oauth_login_use_case(
    oauth_account_repo: OAuthAccountRepo,
    tenant_repo: TenantRepo,
    user_repo: UserRepo,
    refresh_token_repo: RefreshTokenRepo,
    token_service: TokenServiceDep,
    audit_logger: AuditLoggerDep,
) -> OAuthLoginUseCase:
    return OAuthLoginUseCase(
        oauth_account_repo=oauth_account_repo,
        tenant_repo=tenant_repo,
        user_repo=user_repo,
        refresh_token_repo=refresh_token_repo,
        token_service=token_service,
        audit_logger=audit_logger,
    )


RegisterUseCaseDep = Annotated[RegisterUserUseCase, Depends(get_register_use_case)]
LoginUseCaseDep = Annotated[LoginUserUseCase, Depends(get_login_use_case)]
RefreshUseCaseDep = Annotated[RefreshAccessTokenUseCase, Depends(get_refresh_use_case)]
LogoutUseCaseDep = Annotated[LogoutUserUseCase, Depends(get_logout_use_case)]
OAuthLoginUseCaseDep = Annotated[OAuthLoginUseCase, Depends(get_oauth_login_use_case)]
