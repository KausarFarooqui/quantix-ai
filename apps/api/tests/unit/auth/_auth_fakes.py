"""In-memory fake repositories/services for fast, DB-free use-case tests.

These duck-type the domain repository ports (structural typing — Python
doesn't check ABC inheritance at call time) rather than subclassing them,
which keeps each fake to the handful of methods a given test actually
exercises.

Named ``_auth_fakes.py`` (not the generic ``_fakes.py``) because pytest's
default rootless import mode inserts each test directory into ``sys.path``
and caches modules by bare name in ``sys.modules`` — multiple same-named
``_fakes.py`` files across different test directories collide, and
whichever gets imported first silently wins for every other directory
too. Every fakes module in this test tree has a directory-unique name for
that reason (see ``tests/unit/connectors/_connector_fakes.py`` and
``tests/unit/agents/_agent_fakes.py``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from quantix_api.domain.entities.oauth_account import OAuthAccount, OAuthProviderName
from quantix_api.domain.entities.refresh_token import RefreshToken
from quantix_api.domain.entities.tenant import Tenant
from quantix_api.domain.entities.user import User
from quantix_api.domain.exceptions.base import EntityNotFoundError


class FakeTenantRepository:
    def __init__(self) -> None:
        self.store: dict[UUID, Tenant] = {}

    async def get_by_id(self, entity_id: UUID) -> Tenant | None:
        return self.store.get(entity_id)

    async def add(self, entity: Tenant) -> Tenant:
        self.store[entity.id] = entity
        return entity

    async def update(self, entity: Tenant) -> Tenant:
        if entity.id not in self.store:
            raise EntityNotFoundError("Tenant", entity.id)
        self.store[entity.id] = entity
        return entity

    async def delete(self, entity_id: UUID) -> None:
        self.store.pop(entity_id, None)

    async def get_by_slug(self, slug: str) -> Tenant | None:
        return next((t for t in self.store.values() if t.slug == slug), None)

    async def slug_exists(self, slug: str) -> bool:
        return any(t.slug == slug for t in self.store.values())


class FakeUserRepository:
    def __init__(self) -> None:
        self.store: dict[UUID, User] = {}

    async def get_by_id(self, entity_id: UUID) -> User | None:
        return self.store.get(entity_id)

    async def add(self, entity: User) -> User:
        self.store[entity.id] = entity
        return entity

    async def update(self, entity: User) -> User:
        if entity.id not in self.store:
            raise EntityNotFoundError("User", entity.id)
        self.store[entity.id] = entity
        return entity

    async def delete(self, entity_id: UUID) -> None:
        self.store.pop(entity_id, None)

    async def get_by_email(self, tenant_id: UUID, email: str) -> User | None:
        return next(
            (u for u in self.store.values() if u.tenant_id == tenant_id and u.email == email),
            None,
        )

    async def email_exists_in_any_tenant(self, email: str) -> bool:
        return any(u.email == email for u in self.store.values())


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self.store: dict[UUID, RefreshToken] = {}

    async def get_by_id(self, entity_id: UUID) -> RefreshToken | None:
        return self.store.get(entity_id)

    async def add(self, entity: RefreshToken) -> RefreshToken:
        self.store[entity.id] = entity
        return entity

    async def update(self, entity: RefreshToken) -> RefreshToken:
        if entity.id not in self.store:
            raise EntityNotFoundError("RefreshToken", entity.id)
        self.store[entity.id] = entity
        return entity

    async def delete(self, entity_id: UUID) -> None:
        self.store.pop(entity_id, None)

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        return next((t for t in self.store.values() if t.token_hash == token_hash), None)

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        for token in self.store.values():
            if token.user_id == user_id:
                token.revoke()


class FakeOAuthAccountRepository:
    def __init__(self) -> None:
        self.store: dict[UUID, OAuthAccount] = {}

    async def get_by_id(self, entity_id: UUID) -> OAuthAccount | None:
        return self.store.get(entity_id)

    async def add(self, entity: OAuthAccount) -> OAuthAccount:
        self.store[entity.id] = entity
        return entity

    async def update(self, entity: OAuthAccount) -> OAuthAccount:
        if entity.id not in self.store:
            raise EntityNotFoundError("OAuthAccount", entity.id)
        self.store[entity.id] = entity
        return entity

    async def delete(self, entity_id: UUID) -> None:
        self.store.pop(entity_id, None)

    async def get_by_provider_identity(
        self, provider: OAuthProviderName, provider_user_id: str
    ) -> OAuthAccount | None:
        return next(
            (
                a
                for a in self.store.values()
                if a.provider == provider and a.provider_user_id == provider_user_id
            ),
            None,
        )

    async def list_for_user(self, user_id: UUID) -> list[OAuthAccount]:
        return [a for a in self.store.values() if a.user_id == user_id]


class FakeAuditLogger:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def record(self, **kwargs: Any) -> None:
        self.records.append(kwargs)
