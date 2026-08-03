"""File-upload, listing, preview, resync, and delete endpoints for datasets.

Live-source dataset creation (``POST /data-sources/{id}/datasets``) lives
in ``routes.data_sources`` instead — it needs a data source to pull from,
whereas everything here operates on a dataset that either already exists
or is being created from an uploaded file with no data source yet chosen.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from quantix_api.domain.entities.dataset import Dataset
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.interface.api.v1.dependencies.auth import CurrentUser
from quantix_api.interface.api.v1.dependencies.connector_use_cases import (
    DatasetPreviewUseCaseDep,
    DeleteDatasetUseCaseDep,
    SyncDatasetUseCaseDep,
    UploadFileDatasetUseCaseDep,
)
from quantix_api.interface.api.v1.dependencies.repositories import DatasetRepo
from quantix_api.interface.api.v1.schemas.connectors import (
    DatasetColumnResponse,
    DatasetPreviewResponse,
    DatasetResponse,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])

MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB — generous for the inline (non-Celery) upload path


def to_dataset_response(dataset: Dataset) -> DatasetResponse:
    return DatasetResponse(
        id=dataset.id,
        data_source_id=dataset.data_source_id,
        name=dataset.name,
        table_identifier=dataset.table_identifier,
        schema_=[
            DatasetColumnResponse(name=c.name, data_type=c.data_type.value, nullable=c.nullable)
            for c in dataset.schema
        ],
        row_count=dataset.row_count,
        size_bytes=dataset.size_bytes,
        status=dataset.status,
        status_message=dataset.status_message,
        last_synced_at=dataset.last_synced_at,
        created_at=dataset.created_at,
    )


@router.post(
    "/upload",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a CSV/Excel/JSON/Parquet file and ingest it as a dataset",
)
async def upload_file_dataset(
    use_case: UploadFileDatasetUseCaseDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    dataset_name: str | None = Form(default=None),
) -> DatasetResponse:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB inline-upload limit; "
            "large sources should go through a live data source sync instead.",
        )

    dataset = await use_case.execute(
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
        filename=file.filename or "upload",
        content=content,
        dataset_name=dataset_name,
    )
    return to_dataset_response(dataset)


@router.get("", response_model=list[DatasetResponse], summary="List datasets for the current tenant")
async def list_datasets(dataset_repo: DatasetRepo, current_user: CurrentUser) -> list[DatasetResponse]:
    datasets = await dataset_repo.list_for_tenant(current_user.tenant_id)
    return [to_dataset_response(d) for d in datasets]


@router.get("/{dataset_id}", response_model=DatasetResponse, summary="Get a single dataset")
async def get_dataset(
    dataset_id: UUID, dataset_repo: DatasetRepo, current_user: CurrentUser
) -> DatasetResponse:
    dataset = await dataset_repo.get_by_id(dataset_id)
    if dataset is None or dataset.tenant_id != current_user.tenant_id:
        raise EntityNotFoundError("Dataset", dataset_id)
    return to_dataset_response(dataset)


@router.get(
    "/{dataset_id}/preview",
    response_model=DatasetPreviewResponse,
    summary="Preview the first rows of a ready dataset",
)
async def preview_dataset(
    dataset_id: UUID,
    use_case: DatasetPreviewUseCaseDep,
    current_user: CurrentUser,
    limit: int = 100,
) -> DatasetPreviewResponse:
    preview = await use_case.execute(tenant_id=current_user.tenant_id, dataset_id=dataset_id, limit=limit)
    return DatasetPreviewResponse(dataset=to_dataset_response(preview.dataset), rows=preview.rows)


@router.post(
    "/{dataset_id}/resync",
    response_model=DatasetResponse,
    summary="Re-pull the latest data for an existing dataset from its source",
)
async def resync_dataset(
    dataset_id: UUID, use_case: SyncDatasetUseCaseDep, current_user: CurrentUser
) -> DatasetResponse:
    dataset = await use_case.resync(
        tenant_id=current_user.tenant_id, dataset_id=dataset_id, actor_user_id=current_user.id
    )
    return to_dataset_response(dataset)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a dataset")
async def delete_dataset(
    dataset_id: UUID, use_case: DeleteDatasetUseCaseDep, current_user: CurrentUser
) -> None:
    await use_case.execute(
        tenant_id=current_user.tenant_id, dataset_id=dataset_id, actor_user_id=current_user.id
    )
