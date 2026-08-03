"""Fixtures for repository integration tests.

Runs against an in-memory SQLite database rather than PostgreSQL — fast
and dependency-free for CI, at the cost of not exercising Postgres-only
behavior (native UUID/JSONB storage, enum types). That's an accepted
trade-off for this suite: it exists to verify repository *logic*
(mapping, uniqueness, lookups), not database-engine fidelity. The models
were deliberately written with cross-dialect types (see
``infrastructure.database.models.base``) specifically so this works.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from quantix_api.infrastructure.database.models import (  # noqa: F401 — registers tables on Base.metadata
    agent_run,
    audit_log,
    conversation,
    data_source,
    dataset,
    message,
    oauth_account,
    refresh_token,
    tenant,
    user,
)
from quantix_api.infrastructure.database.models.base import Base


@pytest.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()
