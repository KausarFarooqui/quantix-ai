"""OAuth login/signup.

Resolution order on callback:
1. Look up the (provider, provider_user_id) pair directly — if it exists,
   this is a returning user; no tenant lookup needed since the OAuth
   account already points at one.
2. Otherwise, this is a first-time OAuth sign-in: provision a brand-new
   tenant (same as email/password registration) and link the OAuth
   identity to the new owner user.

There is no "link this OAuth provider to my existing password account"
flow yet (that requires the user to be authenticated first, which the
OAuth callback isn't) — tracked as a follow-up in ADR-0002.
"""

from __future__ import annotations

from uuid import UUID

from quantix_api.application.dto.auth import AuthResult
from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.application.interfaces.oauth_provider import OAuthUserInfo
from quantix_api.application.interfaces.token_service import TokenService
from quantix_api.application.use_cases._slug import generate_unique_slug
from quantix_api.application.use_cases._token_issuance import issue_tokens
from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.domain.entities.oauth_account import OAuthAccount, OAuthProviderName
from quantix_api.domain.entities.tenant import Tenant
from quantix_api.domain.entities.user import User, UserRole
from quantix_api.domain.exceptions.auth import InactiveUserError
from quantix_api.domain.exceptions.base import TenantSuspendedError
from quantix_api.domain.repositories.oauth_account_repository import OAuthAccountRepository
from quantix_api.domain.repositories.refresh_token_repository import RefreshTokenRepository
from quantix_api.domain.repositories.tenant_repository import TenantRepository
from quantix_api.domain.repositories.user_repository import UserRepository


class OAuthLoginUseCase:
    def __init__(
        self,
        *,
        oauth_account_repo: OAuthAccountRepository,
        tenant_repo: TenantRepository,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
        token_service: TokenService,
        audit_logger: AuditLogger,
    ) -> None:
        self._oauth_account_repo = oauth_account_repo
        self._tenant_repo = tenant_repo
        self._user_repo = user_repo
        self._refresh_token_repo = refresh_token_repo
        self._token_service = token_service
        self._audit_logger = audit_logger

    async def execute(
        self,
        *,
        provider: OAuthProviderName,
        user_info: OAuthUserInfo,
        organization_name_hint: str | None,
        ip_address: str | None = None,
    ) -> AuthResult:
        existing_link = await self._oauth_account_repo.get_by_provider_identity(
            provider, user_info.provider_user_id
        )

        if existing_link is not None:
            return await self._login_existing(existing_link.user_id, ip_address=ip_address)

        return await self._signup_new(
            provider=provider,
            user_info=user_info,
            organization_name_hint=organization_name_hint,
            ip_address=ip_address,
        )

    async def _login_existing(self, user_id: UUID, *, ip_address: str | None) -> AuthResult:
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise InactiveUserError
        if not user.is_active:
            raise InactiveUserError

        tenant = await self._tenant_repo.get_by_id(user.tenant_id)
        if tenant is not None and not tenant.is_active:
            raise TenantSuspendedError(tenant.id)

        tokens = await issue_tokens(
            user=user, token_service=self._token_service, refresh_token_repo=self._refresh_token_repo
        )
        await self._audit_logger.record(
            action=AuditAction.USER_OAUTH_LOGIN_SUCCEEDED,
            tenant_id=user.tenant_id,
            actor_user_id=user.id,
            ip_address=ip_address,
        )
        return AuthResult(tokens=tokens, user_id=user.id, tenant_id=user.tenant_id)

    async def _signup_new(
        self,
        *,
        provider: OAuthProviderName,
        user_info: OAuthUserInfo,
        organization_name_hint: str | None,
        ip_address: str | None,
    ) -> AuthResult:
        organization_name = organization_name_hint or f"{user_info.full_name}'s workspace"
        slug = await generate_unique_slug(organization_name, self._tenant_repo)
        tenant = await self._tenant_repo.add(Tenant(name=organization_name, slug=slug))

        user = User(
            tenant_id=tenant.id,
            email=user_info.email.lower(),
            hashed_password=None,
            full_name=user_info.full_name,
            role=UserRole.OWNER,
            is_active=True,
            is_email_verified=user_info.email_verified,
        )
        user = await self._user_repo.add(user)

        await self._oauth_account_repo.add(
            OAuthAccount(
                user_id=user.id,
                provider=provider,
                provider_user_id=user_info.provider_user_id,
                email_at_provider=user_info.email,
            )
        )

        tokens = await issue_tokens(
            user=user, token_service=self._token_service, refresh_token_repo=self._refresh_token_repo
        )

        await self._audit_logger.record(
            action=AuditAction.TENANT_CREATED,
            tenant_id=tenant.id,
            actor_user_id=user.id,
            ip_address=ip_address,
        )
        await self._audit_logger.record(
            action=AuditAction.USER_OAUTH_LOGIN_SUCCEEDED,
            tenant_id=tenant.id,
            actor_user_id=user.id,
            metadata={"provider": provider.value, "new_account": True},
            ip_address=ip_address,
        )

        return AuthResult(
            tokens=tokens, user_id=user.id, tenant_id=tenant.id, is_new_account=True
        )
