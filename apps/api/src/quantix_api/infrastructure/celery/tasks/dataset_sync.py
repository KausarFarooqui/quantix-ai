"""Celery task: run ingestion for an already-created (PENDING) dataset.

Thin wrapper — all it does is construct request-scoped-equivalent
dependencies for a Celery worker process (which has no HTTP request to
hang a DB session off) and drive the async ``SyncDatasetUseCase.resync``
to completion with ``asyncio.run``. The use case itself has no idea it's
running inside Celery; the same code path is exercised directly (no
Celery involved) in tests and in the synchronous small-file upload flow.

The dataset row is created synchronously by the route handler
(``SyncDatasetUseCase.create_pending``) *before* this task is dispatched,
so the client gets an ID to poll immediately — this task only does the
(potentially slow) extraction against that existing row.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from quantix_api.application.use_cases.sync_dataset import SyncDatasetUseCase
from quantix_api.core.config import get_settings
from quantix_api.core.container import get_container
from quantix_api.infrastructure.celery.app import app
from quantix_api.infrastructure.database.repositories.audit_log_repository import (
    SqlAlchemyAuditLogRepository,
)
from quantix_api.infrastructure.database.repositories.data_source_repository import (
    SqlAlchemyDataSourceRepository,
)
from quantix_api.infrastructure.database.repositories.dataset_repository import (
    SqlAlchemyDatasetRepository,
)
from quantix_api.infrastructure.database.session import create_engine, create_session_factory
from quantix_api.infrastructure.logging.audit_logger import DatabaseAuditLogger


@app.task(name="quantix.sync_dataset", bind=True, max_retries=2, default_retry_delay=30)
def sync_dataset_task(
    self,  # noqa: ANN001 — bound Celery task instance
    *,
    tenant_id: str,
    dataset_id: str,
    actor_user_id: str,
) -> str:
    """Returns the (now READY or FAILED) dataset's ID as a string."""
    return asyncio.run(
        _run(
            tenant_id=UUID(tenant_id),
            dataset_id=UUID(dataset_id),
            actor_user_id=UUID(actor_user_id),
        )
    )


async def _run(*, tenant_id: UUID, dataset_id: UUID, actor_user_id: UUID) -> str:
    settings = get_settings()
    container = get_container()  # cipher/connector_factory/dataset_storage are process-wide singletons

    # A Celery worker is a separate process from the API server, so it
    # gets its own short-lived engine/session rather than sharing the
    # request-scoped one FastAPI hands out.
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        use_case = SyncDatasetUseCase(
            data_source_repo=SqlAlchemyDataSourceRepository(session),
            dataset_repo=SqlAlchemyDatasetRepository(session),
            dataset_storage=container.dataset_storage,
            connector_factory=container.connector_factory,
            cipher=container.credential_cipher,
            audit_logger=DatabaseAuditLogger(SqlAlchemyAuditLogRepository(session)),
        )
        dataset = await use_case.resync(
            tenant_id=tenant_id, dataset_id=dataset_id, actor_user_id=actor_user_id
        )
        await session.commit()

    await engine.dispose()
    return str(dataset.id)
