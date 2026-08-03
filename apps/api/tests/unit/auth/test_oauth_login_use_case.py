"""Unit tests for OAuthLoginUseCase — first-time signup vs. returning-user paths."""

from __future__ import annotations

from _auth_fakes import (
    FakeAuditLogger,
    FakeOAuthAccountRepository,
    FakeRefreshTokenRepository,
    FakeTenantRepository,
    FakeUserRepository,
)

from quantix_api.application.interfaces.oauth_provider import OAuthUserInfo
from quantix_api.application.use_cases.oauth_login import OAuthLoginUseCase
from quantix_api.domain.entities.oauth_account import OAuthProviderName
from quantix_api.infrastructure.security.jwt_service import JWTTokenService

USER_INFO = OAuthUserInfo(
    provider_user_id="google-subject-123",
    email="ada@example.com",
    email_verified=True,
    full_name="Ada Lovelace",
)


class _Fixture:
    def __init__(self) -> None:
        self.oauth_account_repo = FakeOAuthAccountRepository()
        self.tenant_repo = FakeTenantRepository()
        self.user_repo = FakeUserRepository()
        self.refresh_token_repo = FakeRefreshTokenRepository()
        self.audit_logger = FakeAuditLogger()
        self.use_case = OAuthLoginUseCase(
            oauth_account_repo=self.oauth_account_repo,
            tenant_repo=self.tenant_repo,
            user_repo=self.user_repo,
            refresh_token_repo=self.refresh_token_repo,
            token_service=JWTTokenService(
                secret_key="test-secret", algorithm="HS256", access_token_expire_minutes=30
            ),
            audit_logger=self.audit_logger,
        )


class TestOAuthLoginUseCase:
    async def test_first_time_login_provisions_a_new_tenant_and_owner(self) -> None:
        fx = _Fixture()

        result = await fx.use_case.execute(
            provider=OAuthProviderName.GOOGLE,
            user_info=USER_INFO,
            organization_name_hint="Ada's Company",
        )

        assert result.is_new_account is True
        tenant = await fx.tenant_repo.get_by_id(result.tenant_id)
        assert tenant is not None
        assert tenant.slug == "ada-s-company"

        user = await fx.user_repo.get_by_id(result.user_id)
        assert user is not None
        assert user.hashed_password is None  # OAuth-only account
        assert user.is_email_verified is True

    async def test_falls_back_to_a_generated_workspace_name_without_a_hint(self) -> None:
        fx = _Fixture()

        result = await fx.use_case.execute(
            provider=OAuthProviderName.GITHUB, user_info=USER_INFO, organization_name_hint=None
        )

        tenant = await fx.tenant_repo.get_by_id(result.tenant_id)
        assert "workspace" in tenant.slug

    async def test_returning_user_logs_into_existing_tenant(self) -> None:
        fx = _Fixture()
        first = await fx.use_case.execute(
            provider=OAuthProviderName.GOOGLE,
            user_info=USER_INFO,
            organization_name_hint="Ada's Company",
        )

        second = await fx.use_case.execute(
            provider=OAuthProviderName.GOOGLE, user_info=USER_INFO, organization_name_hint=None
        )

        assert second.is_new_account is False
        assert second.user_id == first.user_id
        assert second.tenant_id == first.tenant_id
        # No second tenant should have been created.
        assert len(fx.tenant_repo.store) == 1

    async def test_different_providers_with_the_same_email_create_separate_accounts(self) -> None:
        # By design (documented in ADR-0002): OAuth identity resolution is
        # keyed on (provider, provider_user_id), not email, so there's no
        # implicit account linking across providers in this milestone.
        fx = _Fixture()
        google_result = await fx.use_case.execute(
            provider=OAuthProviderName.GOOGLE, user_info=USER_INFO, organization_name_hint="Org A"
        )
        github_info = OAuthUserInfo(
            provider_user_id="github-subject-456",
            email=USER_INFO.email,
            email_verified=True,
            full_name=USER_INFO.full_name,
        )
        github_result = await fx.use_case.execute(
            provider=OAuthProviderName.GITHUB, user_info=github_info, organization_name_hint="Org B"
        )

        assert google_result.user_id != github_result.user_id
        assert google_result.tenant_id != github_result.tenant_id
