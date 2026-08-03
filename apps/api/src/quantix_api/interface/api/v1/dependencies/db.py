"""FastAPI dependencies for database access."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from quantix_api.core.container import get_container


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped ``AsyncSession``; commits on success, rolls
    back on exception, always closes.
    """
    container = get_container()
    session = container.session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


DbSession = Annotated[AsyncSession, Depends(get_db_session)]
