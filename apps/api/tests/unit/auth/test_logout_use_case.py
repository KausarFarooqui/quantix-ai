"""Unit tests for LogoutUserUseCase."""

from __future__ import annotations

from uuid import uuid4

from _auth_fakes import FakeAuditLogger, FakeRefreshTokenRepository

from quantix_api.application.use_cases._token_issuance import issue_tokens
from quantix_api.application.use_cases.logout_user import LogoutUserUseCase
from quantix_api.domain.entities.user import User, UserRole
from quantix_api.infrastructure.security.jwt_service import JWTTokenService


class TestLogoutUserUseCase:
    async def _build(self) -> tuple[LogoutUserUseCase, FakeRefreshTokenRepository, JWTTokenService]:
        refresh_token_repo = FakeRefreshTokenRepository()
        token_service = JWTTokenService(
            secret_key="test-secret", algorithm="HS256", access_token_expire_minutes=30
        )
        use_case = LogoutUserUseCase(
            refresh_token_repo=refresh_token_repo,
            token_service=token_service,
            audit_logger=FakeAuditLogger(),
        )
        return use_case, refresh_token_repo, token_service

    async def test_logout_revokes_the_refresh_token(self) -> None:
        use_case, refresh_token_repo, token_service = await self._build()
        user = User(
            tenant_id=uuid4(),
            email="u@acme.com",
            hashed_password="x",
            full_name="U",
            role=UserRole.VIEWER,
        )
        tokens = await issue_tokens(
            user=user, token_service=token_service, refresh_token_repo=refresh_token_repo
        )

        await use_case.execute(
            tokens.refresh_token, actor_user_id=user.id, tenant_id=user.tenant_id
        )

        record = await refresh_token_repo.get_by_token_hash(
            token_service.hash_refresh_token(tokens.refresh_token)
        )
        assert record is not None
        assert record.is_revoked is True

    async def test_logout_with_unknown_token_does_not_raise(self) -> None:
        use_case, *_ = await self._build()

        # Idempotent by design — should not raise even though nothing matches.
        await use_case.execute("no-such-token", actor_user_id=uuid4(), tenant_id=uuid4())
