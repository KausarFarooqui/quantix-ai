"""Unit tests for RegisterUserUseCase — pure in-memory fakes, no DB."""

from __future__ import annotations

import pytest
from _auth_fakes import (
    FakeAuditLogger,
    FakeRefreshTokenRepository,
    FakeTenantRepository,
    FakeUserRepository,
)

from quantix_api.application.dto.auth import RegisterInput
from quantix_api.application.use_cases.register_user import RegisterUserUseCase
from quantix_api.domain.entities.user import UserRole
from quantix_api.domain.exceptions.base import EntityAlreadyExistsError
from quantix_api.infrastructure.security.jwt_service import JWTTokenService
from quantix_api.infrastructure.security.password_hasher import Argon2PasswordHasher


def _build_use_case() -> tuple[RegisterUserUseCase, FakeUserRepository, FakeTenantRepository, FakeAuditLogger]:
    tenant_repo = FakeTenantRepository()
    user_repo = FakeUserRepository()
    refresh_token_repo = FakeRefreshTokenRepository()
    audit_logger = FakeAuditLogger()
    use_case = RegisterUserUseCase(
        tenant_repo=tenant_repo,
        user_repo=user_repo,
        refresh_token_repo=refresh_token_repo,
        password_hasher=Argon2PasswordHasher(),
        token_service=JWTTokenService(
            secret_key="test-secret", algorithm="HS256", access_token_expire_minutes=30
        ),
        audit_logger=audit_logger,
    )
    return use_case, user_repo, tenant_repo, audit_logger


class TestRegisterUserUseCase:
    async def test_creates_tenant_and_owner_user(self) -> None:
        use_case, user_repo, tenant_repo, _ = _build_use_case()

        result = await use_case.execute(
            RegisterInput(
                organization_name="Acme Corp",
                email="founder@acme.com",
                password="correct horse battery staple",
                full_name="Ada Founder",
            )
        )

        assert result.is_new_account is True
        tenant = await tenant_repo.get_by_id(result.tenant_id)
        assert tenant is not None
        assert tenant.slug == "acme-corp"

        user = await user_repo.get_by_id(result.user_id)
        assert user is not None
        assert user.role is UserRole.OWNER
        assert user.email == "founder@acme.com"
        assert user.hashed_password is not None
        assert user.hashed_password != "correct horse battery staple"

    async def test_returns_usable_token_pair(self) -> None:
        use_case, *_ = _build_use_case()

        result = await use_case.execute(
            RegisterInput(
                organization_name="Acme Corp",
                email="founder@acme.com",
                password="correct horse battery staple",
                full_name="Ada Founder",
            )
        )

        assert result.tokens.access_token
        assert result.tokens.refresh_token
        assert result.tokens.expires_in > 0

    async def test_duplicate_email_raises(self) -> None:
        use_case, *_ = _build_use_case()
        payload = RegisterInput(
            organization_name="Acme Corp",
            email="founder@acme.com",
            password="correct horse battery staple",
            full_name="Ada Founder",
        )
        await use_case.execute(payload)

        with pytest.raises(EntityAlreadyExistsError):
            await use_case.execute(
                RegisterInput(
                    organization_name="Another Org",
                    email="founder@acme.com",
                    password="a different password entirely",
                    full_name="Someone Else",
                )
            )

    async def test_records_audit_events(self) -> None:
        use_case, _, _, audit_logger = _build_use_case()

        await use_case.execute(
            RegisterInput(
                organization_name="Acme Corp",
                email="founder@acme.com",
                password="correct horse battery staple",
                full_name="Ada Founder",
            )
        )

        actions = [r["action"].value for r in audit_logger.records]
        assert "tenant.created" in actions
        assert "user.registered" in actions

    async def test_two_orgs_with_the_same_name_get_distinct_slugs(self) -> None:
        use_case, _, tenant_repo, _ = _build_use_case()

        first = await use_case.execute(
            RegisterInput(
                organization_name="Acme Corp",
                email="one@acme.com",
                password="correct horse battery staple",
                full_name="One",
            )
        )
        second = await use_case.execute(
            RegisterInput(
                organization_name="Acme Corp",
                email="two@acme.com",
                password="correct horse battery staple",
                full_name="Two",
            )
        )

        first_tenant = await tenant_repo.get_by_id(first.tenant_id)
        second_tenant = await tenant_repo.get_by_id(second.tenant_id)
        assert first_tenant.slug != second_tenant.slug
