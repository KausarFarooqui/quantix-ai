"""Async SQLAlchemy engine/session factory.

A single engine is created per process and reused across requests; each
request gets its own ``AsyncSession`` from the sessionmaker via the
``get_db_session`` FastAPI dependency (see ``interface.api.v1.dependencies``).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from quantix_api.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Build the async engine with pool sizing driven by settings."""
    return create_async_engine(
        settings.database_url,
        echo=settings.debug and not settings.is_production,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        future=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build a session factory bound to ``engine``."""
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
        class_=AsyncSession,
    )


@asynccontextmanager
async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional session scope: commit on success, rollback
    on any exception, always close.
    """
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
