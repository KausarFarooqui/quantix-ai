"""Unit tests for domain entities — pure Python, no DB/framework needed."""

from __future__ import annotations

from uuid import uuid4

import pytest

from quantix_api.domain.entities.tenant import Tenant, TenantStatus
from quantix_api.domain.entities.user import User, UserRole


class TestTenant:
    def test_new_tenant_defaults_to_active(self) -> None:
        tenant = Tenant(name="Acme Corp", slug="acme")
        assert tenant.is_active is True
        assert tenant.status is TenantStatus.ACTIVE

    def test_suspend_then_activate_round_trips(self) -> None:
        tenant = Tenant(name="Acme Corp", slug="acme")
        tenant.suspend()
        assert tenant.is_active is False
        tenant.activate()
        assert tenant.is_active is True

    def test_entities_with_same_id_are_equal(self) -> None:
        shared_id = uuid4()
        first = Tenant(id=shared_id, name="Acme", slug="acme")
        second = Tenant(id=shared_id, name="Acme Renamed", slug="acme-2")
        assert first == second


class TestUser:
    @pytest.mark.parametrize(
        ("actual_role", "required_role", "expected"),
        [
            (UserRole.OWNER, UserRole.ADMIN, True),
            (UserRole.ADMIN, UserRole.ADMIN, True),
            (UserRole.VIEWER, UserRole.ANALYST, False),
            (UserRole.ANALYST, UserRole.VIEWER, True),
        ],
    )
    def test_has_at_least_role_ranking(
        self, actual_role: UserRole, required_role: UserRole, expected: bool
    ) -> None:
        user = User(
            tenant_id=uuid4(),
            email="user@example.com",
            hashed_password="hashed",
            full_name="Test User",
            role=actual_role,
        )
        assert user.has_at_least(required_role) is expected
