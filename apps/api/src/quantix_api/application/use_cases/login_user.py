"""Email/password login, scoped to a single tenant.

Every failure path — unknown tenant, unknown email, wrong password,
OAuth-only account — collapses to the same ``InvalidCredentialsError`` so
the API response can't be used to enumerate which of those is true. Audit
logging still records the specific reason server-side for investigation.
"""

from __future__ import annotations

from quantix_api.application.dto.auth import AuthResult, LoginInput
from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.application.interfaces.password_hasher import PasswordHasher
from quantix_api.application.interfaces.token_service import TokenService
from quantix_api.application.use_cases._token_issuance import issue_tokens
from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.domain.exceptions.auth import InactiveUserError, InvalidCredentialsError
from quantix_api.domain.exceptions.base import TenantSuspendedError
from quantix_api.domain.repositories.refresh_token_repository import RefreshTokenRepository
from quantix_api.domain.repositories.tenant_repository import TenantRepository
from quantix_api.domain.repositories.user_repository import UserRepository


class LoginUserUseCase:
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

    async def execute(self, data: LoginInput) -> AuthResult:
        tenant = await self._tenant_repo.get_by_slug(data.tenant_slug)
        if tenant is None:
            await self._audit_logger.record(
                action=AuditAction.USER_LOGIN_FAILED,
                tenant_id=None,
                actor_user_id=None,
                metadata={"reason": "unknown_tenant", "tenant_slug": data.tenant_slug},
                ip_address=data.ip_address,
            )
            raise InvalidCredentialsError

        user = await self._user_repo.get_by_email(tenant.id, data.email.lower())
        if user is None or user.hashed_password is None:
            await self._audit_logger.record(
                action=AuditAction.USER_LOGIN_FAILED,
                tenant_id=tenant.id,
                actor_user_id=None,
                metadata={"reason": "unknown_user_or_oauth_only", "email": data.email},
                ip_address=data.ip_address,
            )
            raise InvalidCredentialsError

        if not self._password_hasher.verify(data.password, user.hashed_password):
            await self._audit_logger.record(
                action=AuditAction.USER_LOGIN_FAILED,
                tenant_id=tenant.id,
                actor_user_id=user.id,
                metadata={"reason": "bad_password"},
                ip_address=data.ip_address,
            )
            raise InvalidCredentialsError

        if not tenant.is_active:
            raise TenantSuspendedError(tenant.id)
        if not user.is_active:
            raise InactiveUserError

        if self._password_hasher.needs_rehash(user.hashed_password):
            user.hashed_password = self._password_hasher.hash(data.password)
            user = await self._user_repo.update(user)

        tokens = await issue_tokens(
            user=user, token_service=self._token_service, refresh_token_repo=self._refresh_token_repo
        )

        await self._audit_logger.record(
            action=AuditAction.USER_LOGIN_SUCCEEDED,
            tenant_id=tenant.id,
            actor_user_id=user.id,
            ip_address=data.ip_address,
        )

        return AuthResult(tokens=tokens, user_id=user.id, tenant_id=tenant.id)
