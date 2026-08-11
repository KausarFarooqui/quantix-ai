"""End-to-end API tests for the forecasts endpoints: register a tenant,
upload a dataset with a numeric column, generate a forecast against it,
list and fetch it back — against an in-memory SQLite database, following
the same pattern as ``test_dataset_endpoints.py``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncGenerator, AsyncIterator

os.environ.setdefault("FILE_STORAGE_DIR", tempfile.mkdtemp(prefix="quantix-test-uploads-"))
os.environ.setdefault("DATASET_STORAGE_DIR", tempfile.mkdtemp(prefix="quantix-test-datasets-"))

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from quantix_api.infrastructure.database.models import (  # noqa: F401 — registers tables
    audit_log,
    data_source,
    dataset,
    forecast,
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


async def _registered_access_token(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Acme Corp",
            "email": "founder@acme.com",
            "password": "correct horse battery staple",
            "full_name": "Ada Founder",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


async def _uploaded_dataset_id(client: AsyncClient, headers: dict[str, str]) -> str:
    csv_content = b"day,revenue\n1,100\n2,110\n3,120\n4,130\n"
    response = await client.post(
        "/api/v1/datasets/upload",
        headers=headers,
        files={"file": ("revenue.csv", csv_content, "text/csv")},
        data={"dataset_name": "Revenue"},
    )
    assert response.status_code == 201
    return response.json()["id"]


class TestCreateForecast:
    async def test_generates_and_persists_a_forecast(self, client: AsyncClient) -> None:
        access_token = await _registered_access_token(client)
        headers = {"Authorization": f"Bearer {access_token}"}
        dataset_id = await _uploaded_dataset_id(client, headers)

        response = await client.post(
            "/api/v1/forecasts",
            headers=headers,
            json={"dataset_id": dataset_id, "target_column": "revenue", "periods": 2},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["method"] in ("linear_trend", "holt_winters")
        assert body["historical_points"] == 4
        assert len(body["points"]) == 2
        assert (
            body["points"][0]["lower"] <= body["points"][0]["value"] <= body["points"][0]["upper"]
        )
        assert body["dataset_id"] == dataset_id
        assert body["conversation_id"] is None

    async def test_respects_a_time_column(self, client: AsyncClient) -> None:
        access_token = await _registered_access_token(client)
        headers = {"Authorization": f"Bearer {access_token}"}
        dataset_id = await _uploaded_dataset_id(client, headers)

        response = await client.post(
            "/api/v1/forecasts",
            headers=headers,
            json={
                "dataset_id": dataset_id,
                "target_column": "revenue",
                "time_column": "day",
                "periods": 1,
            },
        )

        assert response.status_code == 201

    async def test_unknown_column_returns_400(self, client: AsyncClient) -> None:
        access_token = await _registered_access_token(client)
        headers = {"Authorization": f"Bearer {access_token}"}
        dataset_id = await _uploaded_dataset_id(client, headers)

        response = await client.post(
            "/api/v1/forecasts",
            headers=headers,
            json={"dataset_id": dataset_id, "target_column": "does_not_exist"},
        )

        assert response.status_code == 400

    async def test_unknown_dataset_returns_404(self, client: AsyncClient) -> None:
        access_token = await _registered_access_token(client)
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await client.post(
            "/api/v1/forecasts",
            headers=headers,
            json={
                "dataset_id": "00000000-0000-0000-0000-000000000000",
                "target_column": "revenue",
            },
        )

        assert response.status_code == 404

    async def test_periods_out_of_range_returns_422(self, client: AsyncClient) -> None:
        access_token = await _registered_access_token(client)
        headers = {"Authorization": f"Bearer {access_token}"}
        dataset_id = await _uploaded_dataset_id(client, headers)

        response = await client.post(
            "/api/v1/forecasts",
            headers=headers,
            json={"dataset_id": dataset_id, "target_column": "revenue", "periods": 0},
        )

        assert response.status_code == 422

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/forecasts",
            json={
                "dataset_id": "00000000-0000-0000-0000-000000000000",
                "target_column": "revenue",
            },
        )

        assert response.status_code == 401

    async def test_rejects_another_tenants_dataset(self, client: AsyncClient) -> None:
        token_a = await _registered_access_token(client)
        dataset_id = await _uploaded_dataset_id(client, {"Authorization": f"Bearer {token_a}"})

        register_b = await client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Widgets Inc",
                "email": "founder@widgets.com",
                "password": "correct horse battery staple",
                "full_name": "Bea Founder",
            },
        )
        token_b = register_b.json()["access_token"]

        response = await client.post(
            "/api/v1/forecasts",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"dataset_id": dataset_id, "target_column": "revenue"},
        )

        assert response.status_code == 404


class TestListAndGetForecasts:
    async def test_list_and_get_round_trip(self, client: AsyncClient) -> None:
        access_token = await _registered_access_token(client)
        headers = {"Authorization": f"Bearer {access_token}"}
        dataset_id = await _uploaded_dataset_id(client, headers)

        create_response = await client.post(
            "/api/v1/forecasts",
            headers=headers,
            json={"dataset_id": dataset_id, "target_column": "revenue", "periods": 2},
        )
        forecast_id = create_response.json()["id"]

        list_response = await client.get("/api/v1/forecasts", headers=headers)
        assert list_response.status_code == 200
        assert any(f["id"] == forecast_id for f in list_response.json())

        filtered_response = await client.get(
            f"/api/v1/forecasts?dataset_id={dataset_id}", headers=headers
        )
        assert filtered_response.status_code == 200
        assert all(f["dataset_id"] == dataset_id for f in filtered_response.json())

        get_response = await client.get(f"/api/v1/forecasts/{forecast_id}", headers=headers)
        assert get_response.status_code == 200
        assert get_response.json()["id"] == forecast_id

    async def test_get_unknown_forecast_returns_404(self, client: AsyncClient) -> None:
        access_token = await _registered_access_token(client)
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await client.get(
            "/api/v1/forecasts/00000000-0000-0000-0000-000000000000", headers=headers
        )

        assert response.status_code == 404

    async def test_another_tenant_cannot_see_the_forecast(self, client: AsyncClient) -> None:
        token_a = await _registered_access_token(client)
        headers_a = {"Authorization": f"Bearer {token_a}"}
        dataset_id = await _uploaded_dataset_id(client, headers_a)
        create_response = await client.post(
            "/api/v1/forecasts",
            headers=headers_a,
            json={"dataset_id": dataset_id, "target_column": "revenue"},
        )
        forecast_id = create_response.json()["id"]

        register_b = await client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Widgets Inc",
                "email": "founder2@widgets.com",
                "password": "correct horse battery staple",
                "full_name": "Cy Founder",
            },
        )
        headers_b = {"Authorization": f"Bearer {register_b.json()['access_token']}"}

        get_response = await client.get(f"/api/v1/forecasts/{forecast_id}", headers=headers_b)
        assert get_response.status_code == 404

        list_response = await client.get("/api/v1/forecasts", headers=headers_b)
        assert list_response.json() == []
