"""Unit tests for LoginUserUseCase."""

from __future__ import annotations

import pytest
from _auth_fakes import (
    FakeAuditLogger,
    FakeRefreshTokenRepository,
    FakeTenantRepository,
    FakeUserRepository,
)

from quantix_api.application.dto.auth import LoginInput
from quantix_api.application.use_cases.login_user import LoginUserUseCase
from quantix_api.domain.entities.tenant import Tenant
from quantix_api.domain.entities.user import User, UserRole
from quantix_api.domain.exceptions.auth import InactiveUserError, InvalidCredentialsError
from quantix_api.domain.exceptions.base import TenantSuspendedError
from quantix_api.infrastructure.security.jwt_service import JWTTokenService
from quantix_api.infrastructure.security.password_hasher import Argon2PasswordHasher

PASSWORD = "correct horse battery staple"


class _Fixture:
    def __init__(self) -> None:
        self.tenant_repo = FakeTenantRepository()
        self.user_repo = FakeUserRepository()
        self.refresh_token_repo = FakeRefreshTokenRepository()
        self.audit_logger = FakeAuditLogger()
        self.hasher = Argon2PasswordHasher()
        self.use_case = LoginUserUseCase(
            tenant_repo=self.tenant_repo,
            user_repo=self.user_repo,
            refresh_token_repo=self.refresh_token_repo,
            password_hasher=self.hasher,
            token_service=JWTTokenService(
                secret_key="test-secret", algorithm="HS256", access_token_expire_minutes=30
            ),
            audit_logger=self.audit_logger,
        )

    async def seed_user(self, **overrides: object) -> tuple[Tenant, User]:
        tenant = Tenant(name="Acme Corp", slug="acme")
        await self.tenant_repo.add(tenant)
        fields: dict[str, object] = {
            "tenant_id": tenant.id,
            "email": "user@acme.com",
            "hashed_password": self.hasher.hash(PASSWORD),
            "full_name": "A User",
            "role": UserRole.ANALYST,
        }
        fields.update(overrides)
        user = User(**fields)  # type: ignore[arg-type]
        await self.user_repo.add(user)
        return tenant, user


class TestLoginUserUseCase:
    async def test_valid_credentials_succeed(self) -> None:
        fx = _Fixture()
        await fx.seed_user()

        result = await fx.use_case.execute(
            LoginInput(tenant_slug="acme", email="user@acme.com", password=PASSWORD)
        )

        assert result.tokens.access_token

    async def test_unknown_tenant_raises_invalid_credentials(self) -> None:
        fx = _Fixture()

        with pytest.raises(InvalidCredentialsError):
            await fx.use_case.execute(
                LoginInput(tenant_slug="no-such-tenant", email="x@x.com", password="whatever")
            )

    async def test_unknown_email_raises_invalid_credentials(self) -> None:
        fx = _Fixture()
        await fx.seed_user()

        with pytest.raises(InvalidCredentialsError):
            await fx.use_case.execute(
                LoginInput(tenant_slug="acme", email="nobody@acme.com", password=PASSWORD)
            )

    async def test_wrong_password_raises_invalid_credentials(self) -> None:
        fx = _Fixture()
        await fx.seed_user()

        with pytest.raises(InvalidCredentialsError):
            await fx.use_case.execute(
                LoginInput(tenant_slug="acme", email="user@acme.com", password="wrong password")
            )

    async def test_oauth_only_account_cannot_login_with_password(self) -> None:
        fx = _Fixture()
        await fx.seed_user(hashed_password=None)

        with pytest.raises(InvalidCredentialsError):
            await fx.use_case.execute(
                LoginInput(tenant_slug="acme", email="user@acme.com", password=PASSWORD)
            )

    async def test_inactive_user_raises(self) -> None:
        fx = _Fixture()
        await fx.seed_user(is_active=False)

        with pytest.raises(InactiveUserError):
            await fx.use_case.execute(
                LoginInput(tenant_slug="acme", email="user@acme.com", password=PASSWORD)
            )

    async def test_suspended_tenant_raises(self) -> None:
        fx = _Fixture()
        tenant, _ = await fx.seed_user()
        tenant.suspend()
        await fx.tenant_repo.update(tenant)

        with pytest.raises(TenantSuspendedError):
            await fx.use_case.execute(
                LoginInput(tenant_slug="acme", email="user@acme.com", password=PASSWORD)
            )

    async def test_failed_login_is_audited(self) -> None:
        fx = _Fixture()
        await fx.seed_user()

        with pytest.raises(InvalidCredentialsError):
            await fx.use_case.execute(
                LoginInput(tenant_slug="acme", email="user@acme.com", password="wrong")
            )

        assert any(r["action"].value == "user.login_failed" for r in fx.audit_logger.records)
