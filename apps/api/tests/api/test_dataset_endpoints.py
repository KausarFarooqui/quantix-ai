"""End-to-end API test for the file-upload dataset flow: register a
tenant, upload a CSV, list it, preview it, then delete it — against an
in-memory SQLite database, following the same httpx AsyncClient +
ASGITransport pattern as ``test_auth_endpoints.py``.

FILE_STORAGE_DIR / DATASET_STORAGE_DIR are pointed at a process-local temp
directory *before* anything imports ``quantix_api.core.config`` (mirroring
how ``tests/conftest.py`` pins SECRET_KEY) — ``get_settings()``/
``get_container()`` are process-wide ``lru_cache`` singletons, so this must
happen at module import time, before any fixture builds the app.
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


class TestFileUploadDatasetFlow:
    async def test_upload_list_preview_delete(self, client: AsyncClient) -> None:
        access_token = await _registered_access_token(client)
        headers = {"Authorization": f"Bearer {access_token}"}
        csv_content = b"id,name,amount\n1,Alice,10.5\n2,Bob,20.25\n3,Cara,30\n"

        upload_response = await client.post(
            "/api/v1/datasets/upload",
            headers=headers,
            files={"file": ("sales.csv", csv_content, "text/csv")},
            data={"dataset_name": "Sales"},
        )

        assert upload_response.status_code == 201
        uploaded = upload_response.json()
        assert uploaded["status"] == "ready"
        assert uploaded["row_count"] == 3
        assert uploaded["name"] == "Sales"
        dataset_id = uploaded["id"]

        list_response = await client.get("/api/v1/datasets", headers=headers)
        assert list_response.status_code == 200
        assert any(d["id"] == dataset_id for d in list_response.json())

        get_response = await client.get(f"/api/v1/datasets/{dataset_id}", headers=headers)
        assert get_response.status_code == 200
        assert get_response.json()["row_count"] == 3

        preview_response = await client.get(
            f"/api/v1/datasets/{dataset_id}/preview", headers=headers
        )
        assert preview_response.status_code == 200
        preview_body = preview_response.json()
        assert len(preview_body["rows"]) == 3
        assert {row["name"] for row in preview_body["rows"]} == {"Alice", "Bob", "Cara"}

        delete_response = await client.delete(f"/api/v1/datasets/{dataset_id}", headers=headers)
        assert delete_response.status_code == 204

        get_after_delete = await client.get(f"/api/v1/datasets/{dataset_id}", headers=headers)
        assert get_after_delete.status_code == 404

    async def test_upload_unsupported_extension_returns_400(self, client: AsyncClient) -> None:
        access_token = await _registered_access_token(client)
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await client.post(
            "/api/v1/datasets/upload",
            headers=headers,
            files={"file": ("archive.zip", b"not a real archive", "application/zip")},
        )

        assert response.status_code == 400

    async def test_preview_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/datasets/00000000-0000-0000-0000-000000000000/preview")
        # HTTPBearer's default auto_error behavior returns 401 for missing
        # credentials; 403 is for authenticated-but-not-permitted requests.
        assert response.status_code == 401

    async def test_upload_rejects_another_tenants_view_of_the_dataset(self, client: AsyncClient) -> None:
        # Tenant A uploads a dataset.
        token_a = await _registered_access_token(client)
        upload_response = await client.post(
            "/api/v1/datasets/upload",
            headers={"Authorization": f"Bearer {token_a}"},
            files={"file": ("sales.csv", b"id\n1\n", "text/csv")},
        )
        dataset_id = upload_response.json()["id"]

        # A second tenant registers separately and must not be able to see it.
        register_b = await client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Globex Corp",
                "email": "founder@globex.com",
                "password": "correct horse battery staple",
                "full_name": "Hank Founder",
            },
        )
        token_b = register_b.json()["access_token"]

        response = await client.get(
            f"/api/v1/datasets/{dataset_id}", headers={"Authorization": f"Bearer {token_b}"}
        )
        assert response.status_code == 404
