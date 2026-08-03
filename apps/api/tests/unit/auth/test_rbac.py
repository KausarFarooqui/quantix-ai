"""Unit tests for the `require_role` RBAC dependency."""

from __future__ import annotations

from uuid import uuid4

import pytest

from quantix_api.domain.entities.user import User, UserRole
from quantix_api.domain.exceptions.base import AuthorizationError
from quantix_api.interface.api.v1.dependencies.auth import require_role


def _user(role: UserRole) -> User:
    return User(
        tenant_id=uuid4(),
        email="u@acme.com",
        hashed_password="x",
        full_name="U",
        role=role,
    )


class TestRequireRole:
    async def test_exact_role_match_passes(self) -> None:
        check = require_role(UserRole.ADMIN)
        user = _user(UserRole.ADMIN)

        result = await check(current_user=user)

        assert result is user

    async def test_higher_role_passes(self) -> None:
        check = require_role(UserRole.ANALYST)
        user = _user(UserRole.OWNER)

        assert await check(current_user=user) is user

    async def test_lower_role_is_rejected(self) -> None:
        check = require_role(UserRole.ADMIN)
        user = _user(UserRole.VIEWER)

        with pytest.raises(AuthorizationError):
            await check(current_user=user)
