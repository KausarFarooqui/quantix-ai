"""Unit tests for DemoLoginUseCase — pure in-memory fakes, no DB."""

from __future__ import annotations

from _auth_fakes import (
    FakeAuditLogger,
    FakeRefreshTokenRepository,
    FakeTenantRepository,
    FakeUserRepository,
)

from quantix_api.application.use_cases.demo_login import (
    DEMO_TENANT_SLUG,
    DEMO_USER_EMAIL,
    DemoLoginUseCase,
)
from quantix_api.domain.entities.user import UserRole
from quantix_api.infrastructure.security.jwt_service import JWTTokenService
from quantix_api.infrastructure.security.password_hasher import Argon2PasswordHasher


def _build_use_case() -> tuple[
    DemoLoginUseCase, FakeUserRepository, FakeTenantRepository, FakeAuditLogger
]:
    tenant_repo = FakeTenantRepository()
    user_repo = FakeUserRepository()
    refresh_token_repo = FakeRefreshTokenRepository()
    audit_logger = FakeAuditLogger()
    use_case = DemoLoginUseCase(
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


class TestDemoLoginUseCase:
    async def test_first_call_creates_demo_tenant_and_owner_user(self) -> None:
        use_case, user_repo, tenant_repo, _ = _build_use_case()

        result = await use_case.execute()

        tenant = await tenant_repo.get_by_id(result.tenant_id)
        assert tenant is not None
        assert tenant.slug == DEMO_TENANT_SLUG

        user = await user_repo.get_by_id(result.user_id)
        assert user is not None
        assert user.email == DEMO_USER_EMAIL
        assert user.role is UserRole.OWNER
        assert user.is_active is True

    async def test_returns_usable_token_pair(self) -> None:
        use_case, *_ = _build_use_case()

        result = await use_case.execute()

        assert result.tokens.access_token
        assert result.tokens.refresh_token
        assert result.tokens.expires_in > 0

    async def test_second_call_reuses_the_same_tenant_and_user(self) -> None:
        use_case, *_ = _build_use_case()

        first = await use_case.execute()
        second = await use_case.execute()

        assert first.tenant_id == second.tenant_id
        assert first.user_id == second.user_id
        # Distinct token pairs each call, same underlying account.
        assert first.tokens.access_token != second.tokens.access_token

    async def test_only_records_creation_audit_events_on_first_call(self) -> None:
        use_case, _, _, audit_logger = _build_use_case()

        await use_case.execute()
        await use_case.execute()

        actions = [r["action"].value for r in audit_logger.records]
        assert actions.count("tenant.created") == 1
        assert actions.count("user.registered") == 1
        # A login-succeeded event fires every call, unlike the creation ones.
        assert actions.count("user.login_succeeded") == 2

    async def test_is_idempotent_when_the_tenant_already_exists_from_elsewhere(self) -> None:
        # Guards against the get-or-create logic assuming it's the only
        # writer — e.g. a concurrent request winning the race to create the
        # demo tenant first.
        use_case, user_repo, tenant_repo, _ = _build_use_case()
        from quantix_api.domain.entities.tenant import Tenant

        pre_existing = await tenant_repo.add(Tenant(name="Demo Workspace", slug=DEMO_TENANT_SLUG))

        result = await use_case.execute()

        assert result.tenant_id == pre_existing.id
        user = await user_repo.get_by_id(result.user_id)
        assert user is not None
        assert user.tenant_id == pre_existing.id
