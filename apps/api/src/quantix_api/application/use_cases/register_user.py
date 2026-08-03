"""Self-serve registration: creates a brand-new tenant and its owner user
in one logical transaction.

There is no "join an existing tenant by email" path yet — that requires an
invitation system, which is out of scope for this milestone (tracked as a
follow-up in ADR-0002). Every registration creates a new workspace.
"""

from __future__ import annotations

from quantix_api.application.dto.auth import AuthResult, RegisterInput
from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.application.interfaces.password_hasher import PasswordHasher
from quantix_api.application.interfaces.token_service import TokenService
from quantix_api.application.use_cases._slug import generate_unique_slug
from quantix_api.application.use_cases._token_issuance import issue_tokens
from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.domain.entities.tenant import Tenant
from quantix_api.domain.entities.user import User, UserRole
from quantix_api.domain.exceptions.base import EntityAlreadyExistsError
from quantix_api.domain.repositories.refresh_token_repository import RefreshTokenRepository
from quantix_api.domain.repositories.tenant_repository import TenantRepository
from quantix_api.domain.repositories.user_repository import UserRepository


class RegisterUserUseCase:
    def __init__(
        self,
        *,
        tenant_repo: TenantRepository,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
        audit_logger: AuditLogger,
    ) -> None:
        self._tenant_repo = tenant_repo
        self._user_repo = user_repo
        self._refresh_token_repo = refresh_token_repo
        self._password_hasher = password_hasher
        self._token_service = token_service
        self._audit_logger = audit_logger

    async def execute(self, data: RegisterInput) -> AuthResult:
        if await self._user_repo.email_exists_in_any_tenant(data.email):
            # Deliberately specific here (unlike login): at registration
            # time there's no credential to protect — telling the user
            # "this email is taken, try logging in" is good UX and leaks
            # nothing an attacker couldn't already learn by trying to
            # register the same address themselves.
            raise EntityAlreadyExistsError("User", "email", data.email)

        slug = await generate_unique_slug(data.organization_name, self._tenant_repo)
        tenant = Tenant(name=data.organization_name, slug=slug)
        tenant = await self._tenant_repo.add(tenant)

        user = User(
            tenant_id=tenant.id,
            email=data.email.lower(),
            hashed_password=self._password_hasher.hash(data.password),
            full_name=data.full_name,
            role=UserRole.OWNER,
            is_active=True,
            is_email_verified=False,
        )
        user = await self._user_repo.add(user)

        tokens = await issue_tokens(
            user=user,
            token_service=self._token_service,
            refresh_token_repo=self._refresh_token_repo,
        )

        await self._audit_logger.record(
            action=AuditAction.TENANT_CREATED,
            tenant_id=tenant.id,
            actor_user_id=user.id,
            resource_type="tenant",
            resource_id=str(tenant.id),
            ip_address=data.ip_address,
        )
        await self._audit_logger.record(
            action=AuditAction.USER_REGISTERED,
            tenant_id=tenant.id,
            actor_user_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
            ip_address=data.ip_address,
        )

        return AuthResult(
            tokens=tokens, user_id=user.id, tenant_id=tenant.id, is_new_account=True
        )
