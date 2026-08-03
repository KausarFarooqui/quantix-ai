"""FastAPI providers assembling the data-connector use cases from
repositories + services. Split from ``dependencies.use_cases`` (which
holds the auth use cases) purely to keep each module focused.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from quantix_api.application.use_cases.create_data_source import CreateDataSourceUseCase
from quantix_api.application.use_cases.delete_data_source import DeleteDataSourceUseCase
from quantix_api.application.use_cases.delete_dataset import DeleteDatasetUseCase
from quantix_api.application.use_cases.discover_data_source_schema import (
    DiscoverDataSourceSchemaUseCase,
)
from quantix_api.application.use_cases.get_dataset_preview import GetDatasetPreviewUseCase
from quantix_api.application.use_cases.sync_dataset import SyncDatasetUseCase
from quantix_api.application.use_cases.test_data_source_connection import (
    TestDataSourceConnectionUseCase,
)
from quantix_api.application.use_cases.upload_file_dataset import UploadFileDatasetUseCase
from quantix_api.interface.api.v1.dependencies.repositories import DataSourceRepo, DatasetRepo
from quantix_api.interface.api.v1.dependencies.services import (
    AuditLoggerDep,
    ConnectorFactoryDep,
    CredentialCipherDep,
    DatasetStorageDep,
    FileStorageDep,
)


def get_create_data_source_use_case(
    data_source_repo: DataSourceRepo, cipher: CredentialCipherDep, audit_logger: AuditLoggerDep
) -> CreateDataSourceUseCase:
    return CreateDataSourceUseCase(
        data_source_repo=data_source_repo, cipher=cipher, audit_logger=audit_logger
    )


def get_test_data_source_connection_use_case(
    data_source_repo: DataSourceRepo,
    cipher: CredentialCipherDep,
    connector_factory: ConnectorFactoryDep,
    audit_logger: AuditLoggerDep,
) -> TestDataSourceConnectionUseCase:
    return TestDataSourceConnectionUseCase(
        data_source_repo=data_source_repo,
        cipher=cipher,
        connector_factory=connector_factory,
        audit_logger=audit_logger,
    )


def get_delete_data_source_use_case(
    data_source_repo: DataSourceRepo,
    dataset_repo: DatasetRepo,
    dataset_storage: DatasetStorageDep,
    file_storage: FileStorageDep,
    audit_logger: AuditLoggerDep,
) -> DeleteDataSourceUseCase:
    return DeleteDataSourceUseCase(
        data_source_repo=data_source_repo,
        dataset_repo=dataset_repo,
        dataset_storage=dataset_storage,
        file_storage=file_storage,
        audit_logger=audit_logger,
    )


def get_discover_data_source_schema_use_case(
    data_source_repo: DataSourceRepo,
    cipher: CredentialCipherDep,
    connector_factory: ConnectorFactoryDep,
) -> DiscoverDataSourceSchemaUseCase:
    return DiscoverDataSourceSchemaUseCase(
        data_source_repo=data_source_repo, cipher=cipher, connector_factory=connector_factory
    )


def get_upload_file_dataset_use_case(
    data_source_repo: DataSourceRepo,
    dataset_repo: DatasetRepo,
    file_storage: FileStorageDep,
    dataset_storage: DatasetStorageDep,
    connector_factory: ConnectorFactoryDep,
    audit_logger: AuditLoggerDep,
) -> UploadFileDatasetUseCase:
    return UploadFileDatasetUseCase(
        data_source_repo=data_source_repo,
        dataset_repo=dataset_repo,
        file_storage=file_storage,
        dataset_storage=dataset_storage,
        connector_factory=connector_factory,
        audit_logger=audit_logger,
    )


def get_sync_dataset_use_case(
    data_source_repo: DataSourceRepo,
    dataset_repo: DatasetRepo,
    dataset_storage: DatasetStorageDep,
    connector_factory: ConnectorFactoryDep,
    cipher: CredentialCipherDep,
    audit_logger: AuditLoggerDep,
) -> SyncDatasetUseCase:
    return SyncDatasetUseCase(
        data_source_repo=data_source_repo,
        dataset_repo=dataset_repo,
        dataset_storage=dataset_storage,
        connector_factory=connector_factory,
        cipher=cipher,
        audit_logger=audit_logger,
    )


def get_dataset_preview_use_case(
    dataset_repo: DatasetRepo, dataset_storage: DatasetStorageDep
) -> GetDatasetPreviewUseCase:
    return GetDatasetPreviewUseCase(dataset_repo=dataset_repo, dataset_storage=dataset_storage)


def get_delete_dataset_use_case(
    dataset_repo: DatasetRepo, dataset_storage: DatasetStorageDep, audit_logger: AuditLoggerDep
) -> DeleteDatasetUseCase:
    return DeleteDatasetUseCase(
        dataset_repo=dataset_repo, dataset_storage=dataset_storage, audit_logger=audit_logger
    )


CreateDataSourceUseCaseDep = Annotated[
    CreateDataSourceUseCase, Depends(get_create_data_source_use_case)
]
TestDataSourceConnectionUseCaseDep = Annotated[
    TestDataSourceConnectionUseCase, Depends(get_test_data_source_connection_use_case)
]
DeleteDataSourceUseCaseDep = Annotated[
    DeleteDataSourceUseCase, Depends(get_delete_data_source_use_case)
]
DiscoverDataSourceSchemaUseCaseDep = Annotated[
    DiscoverDataSourceSchemaUseCase, Depends(get_discover_data_source_schema_use_case)
]
UploadFileDatasetUseCaseDep = Annotated[
    UploadFileDatasetUseCase, Depends(get_upload_file_dataset_use_case)
]
SyncDatasetUseCaseDep = Annotated[SyncDatasetUseCase, Depends(get_sync_dataset_use_case)]
DatasetPreviewUseCaseDep = Annotated[
    GetDatasetPreviewUseCase, Depends(get_dataset_preview_use_case)
]
DeleteDatasetUseCaseDep = Annotated[DeleteDatasetUseCase, Depends(get_delete_dataset_use_case)]
