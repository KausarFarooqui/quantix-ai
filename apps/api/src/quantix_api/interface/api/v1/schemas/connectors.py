"""Pydantic request/response schemas for data sources and datasets."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from quantix_api.domain.entities.data_source import DataSourceStatus, SourceType
from quantix_api.domain.entities.dataset import DatasetStatus


class DataSourceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_type: SourceType
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Non-secret connection parameters (host, port, database, project_id, ...).",
    )
    secrets: dict[str, Any] | None = Field(
        default=None,
        description="Sensitive values (password, service_account_json, ...) — encrypted at rest, never returned.",
    )


class DataSourceResponse(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: UUID
    name: str
    source_type: SourceType
    config: dict[str, Any]
    status: DataSourceStatus
    last_tested_at: datetime | None
    last_test_error: str | None
    created_at: datetime


class ConnectionTestResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    success: bool
    error: str | None = None


class DatasetColumnResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    data_type: str
    nullable: bool


class DatasetResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    data_source_id: UUID
    name: str
    table_identifier: str
    schema_: list[DatasetColumnResponse] = Field(serialization_alias="schema")
    row_count: int | None
    size_bytes: int | None
    status: DatasetStatus
    status_message: str | None
    last_synced_at: datetime | None
    created_at: datetime


class DatasetSyncRequest(BaseModel):
    table_identifier: str = Field(
        min_length=1, description="A discovered table/sheet identifier, or a raw SELECT query."
    )
    dataset_name: str | None = None
    run_async: bool = Field(
        default=False,
        description="If true, dispatches ingestion to a Celery worker and returns immediately "
        "with a PENDING dataset rather than waiting inline.",
    )


class DatasetPreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset: DatasetResponse
    rows: list[dict[str, Any]]


class TableSchemaResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    identifier: str
    columns: list[DatasetColumnResponse]
    row_count_estimate: int | None
