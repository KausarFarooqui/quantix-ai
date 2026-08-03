"""Unit tests for RefreshAccessTokenUseCase — rotation and reuse detection."""

from __future__ import annotations

import pytest
from _auth_fakes import FakeAuditLogger, FakeRefreshTokenRepository, FakeUserRepository

from quantix_api.application.use_cases._token_issuance import issue_tokens
from quantix_api.application.use_cases.refresh_access_token import RefreshAccessTokenUseCase
from quantix_api.domain.entities.user import User, UserRole
from quantix_api.domain.exceptions.auth import InvalidRefreshTokenError, RefreshTokenReuseError
from quantix_api.infrastructure.security.jwt_service import JWTTokenService
from uuid import uuid4


class _Fixture:
    def __init__(self) -> None:
        self.user_repo = FakeUserRepository()
        self.refresh_token_repo = FakeRefreshTokenRepository()
        self.audit_logger = FakeAuditLogger()
        self.token_service = JWTTokenService(
            secret_key="test-secret", algorithm="HS256", access_token_expire_minutes=30
        )
        self.use_case = RefreshAccessTokenUseCase(
            refresh_token_repo=self.refresh_token_repo,
            user_repo=self.user_repo,
            token_service=self.token_service,
            audit_logger=self.audit_logger,
        )

    async def seed_user_with_tokens(self) -> tuple[User, str]:
        user = User(
            tenant_id=uuid4(),
            email="user@acme.com",
            hashed_password="irrelevant",
            full_name="A User",
            role=UserRole.ANALYST,
        )
        await self.user_repo.add(user)
        tokens = await issue_tokens(
            user=user, token_service=self.token_service, refresh_token_repo=self.refresh_token_repo
        )
        return user, tokens.refresh_token


class TestRefreshAccessTokenUseCase:
    async def test_valid_token_is_rotated(self) -> None:
        fx = _Fixture()
        _, raw_refresh_token = await fx.seed_user_with_tokens()

        result = await fx.use_case.execute(raw_refresh_token)

        assert result.tokens.refresh_token != raw_refresh_token
        assert result.tokens.access_token

    async def test_old_token_is_revoked_after_rotation(self) -> None:
        fx = _Fixture()
        _, raw_refresh_token = await fx.seed_user_with_tokens()
        old_hash = fx.token_service.hash_refresh_token(raw_refresh_token)

        await fx.use_case.execute(raw_refresh_token)

        old_record = await fx.refresh_token_repo.get_by_token_hash(old_hash)
        assert old_record is not None
        assert old_record.is_revoked is True

    async def test_reusing_a_rotated_token_is_detected_and_revokes_everything(self) -> None:
        fx = _Fixture()
        user, raw_refresh_token = await fx.seed_user_with_tokens()
        await fx.use_case.execute(raw_refresh_token)  # first (legitimate) use — rotates it

        with pytest.raises(RefreshTokenReuseError):
            await fx.use_case.execute(raw_refresh_token)  # reuse — should be detected

        # every token for this user should now be revoked, including the
        # freshly rotated one issued by the first call
        all_tokens = [t for t in fx.refresh_token_repo.store.values() if t.user_id == user.id]
        assert all(t.is_revoked for t in all_tokens)

    async def test_unknown_token_raises(self) -> None:
        fx = _Fixture()

        with pytest.raises(InvalidRefreshTokenError):
            await fx.use_case.execute("this-token-does-not-exist")

    async def test_reuse_is_audited(self) -> None:
        fx = _Fixture()
        _, raw_refresh_token = await fx.seed_user_with_tokens()
        await fx.use_case.execute(raw_refresh_token)

        with pytest.raises(RefreshTokenReuseError):
            await fx.use_case.execute(raw_refresh_token)

        assert any(r["action"].value == "token.reuse_detected" for r in fx.audit_logger.records)
