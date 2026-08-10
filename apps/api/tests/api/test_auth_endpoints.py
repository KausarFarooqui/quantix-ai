"""End-to-end API tests for the auth endpoints — register, login,
demo-login, refresh, logout, and /me — against an in-memory SQLite
database wired in via a ``get_db_session`` dependency override (the real
Postgres connection is never touched).

Uses ``httpx.AsyncClient`` over an ``ASGITransport`` rather than Starlette's
synchronous ``TestClient``: everything (schema creation, HTTP calls, and
the DB session opened inside the dependency override) then runs on the
*same* event loop that pytest-asyncio manages for the test. Mixing a sync
TestClient with an async SQLite engine risks connections being opened on
one loop and used from another — this sidesteps that entirely.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from quantix_api.infrastructure.database.models import (  # noqa: F401 — registers tables
    audit_log,
    oauth_account,
    refresh_token,
    tenant,
    user,
)
from quantix_api.infrastructure.database.models.base import Base
from quantix_api.interface.api.v1.dependencies.db import get_db_session


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from quantix_api.main import create_app

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db_session] = _override_get_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client

    await engine.dispose()


def _register_payload(**overrides: str) -> dict[str, str]:
    payload = {
        "organization_name": "Acme Corp",
        "email": "founder@acme.com",
        "password": "correct horse battery staple",
        "full_name": "Ada Founder",
    }
    payload.update(overrides)
    return payload


class TestRegisterEndpoint:
    async def test_register_returns_tokens(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/register", json=_register_payload())

        assert response.status_code == 201
        body = response.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "bearer"

    async def test_duplicate_email_returns_409(self, client: AsyncClient) -> None:
        await client.post("/api/v1/auth/register", json=_register_payload())

        response = await client.post(
            "/api/v1/auth/register",
            json=_register_payload(organization_name="Another Org"),
        )

        assert response.status_code == 409

    async def test_weak_password_is_rejected(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/register", json=_register_payload(password="short")
        )

        assert response.status_code == 422


class TestMeEndpoint:
    async def test_returns_current_user_with_valid_token(self, client: AsyncClient) -> None:
        register_response = await client.post("/api/v1/auth/register", json=_register_payload())
        access_token = register_response.json()["access_token"]

        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200
        assert response.json()["email"] == "founder@acme.com"
        assert response.json()["role"] == "owner"

    async def test_rejects_missing_token(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/auth/me")
        # HTTPBearer's default auto_error behavior returns 401 Unauthorized
        # for missing credentials (no Authorization header at all) — 403
        # Forbidden is reserved for a request that authenticated
        # successfully but isn't permitted to do this.
        assert response.status_code == 401

    async def test_rejects_garbage_token(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert response.status_code == 401


class TestLoginEndpoint:
    async def test_login_with_correct_credentials(self, client: AsyncClient) -> None:
        await client.post("/api/v1/auth/register", json=_register_payload())

        response = await client.post(
            "/api/v1/auth/login",
            json={
                "tenant_slug": "acme-corp",
                "email": "founder@acme.com",
                "password": "correct horse battery staple",
            },
        )

        assert response.status_code == 200
        assert response.json()["access_token"]

    async def test_login_with_wrong_password_returns_401(self, client: AsyncClient) -> None:
        await client.post("/api/v1/auth/register", json=_register_payload())

        response = await client.post(
            "/api/v1/auth/login",
            json={"tenant_slug": "acme-corp", "email": "founder@acme.com", "password": "nope"},
        )

        assert response.status_code == 401


class TestDemoLoginEndpoint:
    """There's no login/signup UI (ADR-0008) — `/auth/demo-login` is the
    app's actual entry point, so it gets the same end-to-end coverage as
    `/auth/register` and `/auth/login` above, not just the use case's unit
    tests.
    """

    async def test_returns_usable_tokens_with_no_body(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/demo-login")

        assert response.status_code == 200
        body = response.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "bearer"

    async def test_the_returned_token_resolves_to_the_demo_user_via_me(
        self, client: AsyncClient
    ) -> None:
        login_response = await client.post("/api/v1/auth/demo-login")
        access_token = login_response.json()["access_token"]

        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200
        assert response.json()["email"] == "demo@quantix.local"
        assert response.json()["role"] == "owner"

    async def test_repeated_calls_reuse_the_same_account(self, client: AsyncClient) -> None:
        first = await client.post("/api/v1/auth/demo-login")
        second = await client.post("/api/v1/auth/demo-login")

        first_user = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {first.json()['access_token']}"},
        )
        second_user = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {second.json()['access_token']}"},
        )

        assert first_user.json()["id"] == second_user.json()["id"]
        assert first_user.json()["tenant_id"] == second_user.json()["tenant_id"]


class TestRefreshAndLogout:
    async def test_refresh_returns_a_new_token_pair(self, client: AsyncClient) -> None:
        register_response = await client.post("/api/v1/auth/register", json=_register_payload())
        refresh_token_value = register_response.json()["refresh_token"]

        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token_value}
        )

        assert response.status_code == 200
        assert response.json()["refresh_token"] != refresh_token_value

    async def test_reusing_a_rotated_refresh_token_is_rejected(self, client: AsyncClient) -> None:
        register_response = await client.post("/api/v1/auth/register", json=_register_payload())
        refresh_token_value = register_response.json()["refresh_token"]
        await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token_value})

        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token_value}
        )

        assert response.status_code == 401

    async def test_logout_then_refresh_fails(self, client: AsyncClient) -> None:
        register_response = await client.post("/api/v1/auth/register", json=_register_payload())
        access_token = register_response.json()["access_token"]
        refresh_token_value = register_response.json()["refresh_token"]

        logout_response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token_value},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert logout_response.status_code == 204

        refresh_response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token_value}
        )
        assert refresh_response.status_code == 401
