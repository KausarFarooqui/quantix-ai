"""CRUD + connection-testing endpoints for data sources."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from quantix_api.domain.entities.data_source import DataSource
from quantix_api.domain.entities.user import User, UserRole
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.interface.api.v1.dependencies.auth import CurrentUser, require_role
from quantix_api.interface.api.v1.dependencies.connector_use_cases import (
    CreateDataSourceUseCaseDep,
    DeleteDataSourceUseCaseDep,
    DiscoverDataSourceSchemaUseCaseDep,
    SyncDatasetUseCaseDep,
    TestDataSourceConnectionUseCaseDep,
)
from quantix_api.interface.api.v1.dependencies.repositories import DataSourceRepo
from quantix_api.interface.api.v1.routes.datasets import to_dataset_response
from quantix_api.interface.api.v1.schemas.connectors import (
    ConnectionTestResponse,
    DataSourceCreateRequest,
    DatasetResponse,
    DatasetSyncRequest,
    DataSourceResponse,
    TableSchemaResponse,
)

router = APIRouter(prefix="/data-sources", tags=["data-sources"])


def _to_response(data_source: DataSource) -> DataSourceResponse:
    return DataSourceResponse(
        id=data_source.id,
        name=data_source.name,
        source_type=data_source.source_type,
        config=data_source.config,
        status=data_source.status,
        last_tested_at=data_source.last_tested_at,
        last_test_error=data_source.last_test_error,
        created_at=data_source.created_at,
    )


@router.post(
    "",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new data source (analysts and above)",
)
async def create_data_source(
    body: DataSourceCreateRequest,
    use_case: CreateDataSourceUseCaseDep,
    current_user: Annotated[User, Depends(require_role(UserRole.ANALYST))],
) -> DataSourceResponse:
    data_source = await use_case.execute(
        tenant_id=current_user.tenant_id,
        name=body.name,
        source_type=body.source_type,
        config=body.config,
        secrets=body.secrets,
        created_by_user_id=current_user.id,
    )
    return _to_response(data_source)


@router.get("", response_model=list[DataSourceResponse], summary="List data sources for the current tenant")
async def list_data_sources(
    data_source_repo: DataSourceRepo, current_user: CurrentUser
) -> list[DataSourceResponse]:
    data_sources = await data_source_repo.list_for_tenant(current_user.tenant_id)
    return [_to_response(ds) for ds in data_sources]


@router.get("/{data_source_id}", response_model=DataSourceResponse, summary="Get a single data source")
async def get_data_source(
    data_source_id: UUID, data_source_repo: DataSourceRepo, current_user: CurrentUser
) -> DataSourceResponse:
    data_source = await data_source_repo.get_by_id(data_source_id)
    if data_source is None or data_source.tenant_id != current_user.tenant_id:
        raise EntityNotFoundError("DataSource", data_source_id)
    return _to_response(data_source)


@router.post(
    "/{data_source_id}/test",
    response_model=ConnectionTestResponse,
    summary="Test connectivity for a data source",
)
async def test_data_source(
    data_source_id: UUID, use_case: TestDataSourceConnectionUseCaseDep, current_user: CurrentUser
) -> ConnectionTestResponse:
    result = await use_case.execute(
        tenant_id=current_user.tenant_id, data_source_id=data_source_id, actor_user_id=current_user.id
    )
    return ConnectionTestResponse(success=result.success, error=result.error)


@router.get(
    "/{data_source_id}/discover",
    response_model=list[TableSchemaResponse],
    summary="List the tables/sheets available on a data source",
)
async def discover_data_source(
    data_source_id: UUID, use_case: DiscoverDataSourceSchemaUseCaseDep, current_user: CurrentUser
) -> list[TableSchemaResponse]:
    tables = await use_case.execute(tenant_id=current_user.tenant_id, data_source_id=data_source_id)
    return [
        TableSchemaResponse(
            identifier=table.identifier,
            columns=[
                {"name": c.name, "data_type": c.data_type.value, "nullable": c.nullable}
                for c in table.columns
            ],
            row_count_estimate=table.row_count_estimate,
        )
        for table in tables
    ]


@router.post(
    "/{data_source_id}/datasets",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Pull a table/sheet/query from this data source into a new dataset",
)
async def sync_dataset_from_source(
    data_source_id: UUID,
    body: DatasetSyncRequest,
    use_case: SyncDatasetUseCaseDep,
    current_user: Annotated[User, Depends(require_role(UserRole.ANALYST))],
) -> DatasetResponse:
    if body.run_async:
        from quantix_api.infrastructure.celery.tasks.dataset_sync import sync_dataset_task

        # The dataset row is created synchronously (PENDING) so the client
        # has an ID to poll immediately; the actual extraction is handed
        # off to a worker. See ADR-0003 for when to prefer this over the
        # inline path below.
        pending_dataset = await use_case.create_pending(
            tenant_id=current_user.tenant_id,
            data_source_id=data_source_id,
            table_identifier=body.table_identifier,
            dataset_name=body.dataset_name,
        )
        sync_dataset_task.delay(
            tenant_id=str(current_user.tenant_id),
            dataset_id=str(pending_dataset.id),
            actor_user_id=str(current_user.id),
        )
        return to_dataset_response(pending_dataset)

    dataset = await use_case.execute(
        tenant_id=current_user.tenant_id,
        data_source_id=data_source_id,
        table_identifier=body.table_identifier,
        dataset_name=body.dataset_name,
        actor_user_id=current_user.id,
    )
    return to_dataset_response(dataset)


@router.delete(
    "/{data_source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a data source and every dataset pulled from it (admins and above)",
)
async def delete_data_source(
    data_source_id: UUID,
    use_case: DeleteDataSourceUseCaseDep,
    current_user: Annotated[User, Depends(require_role(UserRole.ADMIN))],
) -> None:
    await use_case.execute(
        tenant_id=current_user.tenant_id, data_source_id=data_source_id, actor_user_id=current_user.id
    )
