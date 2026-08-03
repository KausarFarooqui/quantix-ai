"""Unit tests for the DataSource use cases: create, test-connection,
delete, and schema discovery — all against fakes.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from _connector_fakes import (
    FakeAuditLogger,
    FakeConnector,
    FakeConnectorFactory,
    FakeCredentialCipher,
    FakeDataSourceRepository,
    FakeDatasetRepository,
    FakeDatasetStorage,
    FakeFileStorage,
)

from quantix_api.application.use_cases.create_data_source import CreateDataSourceUseCase
from quantix_api.application.use_cases.delete_data_source import DeleteDataSourceUseCase
from quantix_api.application.use_cases.discover_data_source_schema import (
    DiscoverDataSourceSchemaUseCase,
)
from quantix_api.application.use_cases.test_data_source_connection import (
    TestDataSourceConnectionUseCase,
)
from quantix_api.domain.entities.data_source import DataSource, DataSourceStatus, SourceType
from quantix_api.domain.entities.dataset import Dataset
from quantix_api.domain.exceptions.base import EntityNotFoundError


class TestCreateDataSourceUseCase:
    async def test_encrypts_secrets_and_persists_pending_source(self) -> None:
        repo = FakeDataSourceRepository()
        cipher = FakeCredentialCipher()
        audit_logger = FakeAuditLogger()
        use_case = CreateDataSourceUseCase(data_source_repo=repo, cipher=cipher, audit_logger=audit_logger)

        data_source = await use_case.execute(
            tenant_id=uuid4(),
            name="Prod Postgres",
            source_type=SourceType.POSTGRESQL,
            config={"host": "db.internal", "port": 5432, "database": "app"},
            secrets={"username": "admin", "password": "s3cret"},
            created_by_user_id=uuid4(),
        )

        assert data_source.status is DataSourceStatus.PENDING
        assert data_source.encrypted_secrets is not None
        assert "s3cret" not in data_source.encrypted_secrets or cipher.decrypt(
            data_source.encrypted_secrets
        ) == {"username": "admin", "password": "s3cret"}
        assert data_source.id in repo.store
        assert any(r["action"].value == "data_source.created" for r in audit_logger.records)

    async def test_no_secrets_leaves_encrypted_secrets_none(self) -> None:
        repo = FakeDataSourceRepository()
        use_case = CreateDataSourceUseCase(
            data_source_repo=repo, cipher=FakeCredentialCipher(), audit_logger=FakeAuditLogger()
        )

        data_source = await use_case.execute(
            tenant_id=uuid4(),
            name="Sample CSV",
            source_type=SourceType.CSV,
            config={},
            secrets=None,
            created_by_user_id=uuid4(),
        )

        assert data_source.encrypted_secrets is None


class TestTestDataSourceConnectionUseCase:
    def _build(self, connector: FakeConnector):
        data_source_repo = FakeDataSourceRepository()
        cipher = FakeCredentialCipher()
        connector_factory = FakeConnectorFactory(connector)
        audit_logger = FakeAuditLogger()
        use_case = TestDataSourceConnectionUseCase(
            data_source_repo=data_source_repo,
            cipher=cipher,
            connector_factory=connector_factory,
            audit_logger=audit_logger,
        )
        return use_case, data_source_repo, audit_logger

    async def test_successful_test_marks_source_active(self) -> None:
        use_case, repo, audit_logger = self._build(FakeConnector())
        tenant_id, user_id = uuid4(), uuid4()
        data_source = await repo.add(
            DataSource(tenant_id=tenant_id, name="db", source_type=SourceType.SQLITE, config={})
        )

        result = await use_case.execute(
            tenant_id=tenant_id, data_source_id=data_source.id, actor_user_id=user_id
        )

        assert result.success is True
        assert repo.store[data_source.id].status is DataSourceStatus.ACTIVE
        assert any(
            r["action"].value == "data_source.connection_tested" for r in audit_logger.records
        )

    async def test_failed_test_marks_source_error_with_message(self) -> None:
        use_case, repo, _ = self._build(FakeConnector(should_fail=True))
        tenant_id = uuid4()
        data_source = await repo.add(
            DataSource(tenant_id=tenant_id, name="db", source_type=SourceType.SQLITE, config={})
        )

        result = await use_case.execute(
            tenant_id=tenant_id, data_source_id=data_source.id, actor_user_id=uuid4()
        )

        assert result.success is False
        stored = repo.store[data_source.id]
        assert stored.status is DataSourceStatus.ERROR
        assert stored.last_test_error == "boom"

    async def test_unknown_data_source_raises_not_found(self) -> None:
        use_case, _repo, _ = self._build(FakeConnector())

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(tenant_id=uuid4(), data_source_id=uuid4(), actor_user_id=uuid4())

    async def test_cross_tenant_access_raises_not_found(self) -> None:
        use_case, repo, _ = self._build(FakeConnector())
        data_source = await repo.add(
            DataSource(tenant_id=uuid4(), name="db", source_type=SourceType.SQLITE, config={})
        )

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(
                tenant_id=uuid4(), data_source_id=data_source.id, actor_user_id=uuid4()
            )


class TestDeleteDataSourceUseCase:
    def _build(self):
        data_source_repo = FakeDataSourceRepository()
        dataset_repo = FakeDatasetRepository()
        dataset_storage = FakeDatasetStorage()
        file_storage = FakeFileStorage()
        audit_logger = FakeAuditLogger()
        use_case = DeleteDataSourceUseCase(
            data_source_repo=data_source_repo,
            dataset_repo=dataset_repo,
            dataset_storage=dataset_storage,
            file_storage=file_storage,
            audit_logger=audit_logger,
        )
        return use_case, data_source_repo, dataset_repo, dataset_storage, file_storage, audit_logger

    async def test_cascades_to_datasets_and_removes_storage(self) -> None:
        use_case, ds_repo, dataset_repo, dataset_storage, _file_storage, audit_logger = self._build()
        tenant_id = uuid4()
        data_source = await ds_repo.add(
            DataSource(tenant_id=tenant_id, name="db", source_type=SourceType.SQLITE, config={})
        )
        storage_uri, _ = dataset_storage.write(
            tenant_id=tenant_id, dataset_id=uuid4(), table=__import__("pyarrow").table({"a": [1]})
        )
        dataset = await dataset_repo.add(
            Dataset(
                tenant_id=tenant_id,
                data_source_id=data_source.id,
                name="orders",
                table_identifier="orders",
                storage_uri=storage_uri,
            )
        )

        await use_case.execute(tenant_id=tenant_id, data_source_id=data_source.id, actor_user_id=uuid4())

        assert data_source.id not in ds_repo.store
        assert dataset.id not in dataset_repo.store
        assert storage_uri not in dataset_storage._tables  # noqa: SLF001
        assert any(r["action"].value == "data_source.deleted" for r in audit_logger.records)

    async def test_deletes_uploaded_file_for_file_based_sources(self) -> None:
        use_case, ds_repo, _dataset_repo, _dataset_storage, file_storage, _audit_logger = self._build()
        tenant_id = uuid4()
        path = file_storage.save(tenant_id=tenant_id, filename="data.csv", content=b"a,b\n1,2\n")
        data_source = await ds_repo.add(
            DataSource(
                tenant_id=tenant_id,
                name="data.csv",
                source_type=SourceType.CSV,
                config={"storage_path": path},
            )
        )

        await use_case.execute(tenant_id=tenant_id, data_source_id=data_source.id, actor_user_id=uuid4())

        assert path not in file_storage._files  # noqa: SLF001

    async def test_unknown_data_source_raises_not_found(self) -> None:
        use_case, *_rest = self._build()

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(tenant_id=uuid4(), data_source_id=uuid4(), actor_user_id=uuid4())


class TestDiscoverDataSourceSchemaUseCase:
    async def test_returns_tables_from_the_connector(self) -> None:
        data_source_repo = FakeDataSourceRepository()
        connector_factory = FakeConnectorFactory(FakeConnector())
        use_case = DiscoverDataSourceSchemaUseCase(
            data_source_repo=data_source_repo,
            cipher=FakeCredentialCipher(),
            connector_factory=connector_factory,
        )
        tenant_id = uuid4()
        data_source = await data_source_repo.add(
            DataSource(tenant_id=tenant_id, name="db", source_type=SourceType.SQLITE, config={})
        )

        tables = await use_case.execute(tenant_id=tenant_id, data_source_id=data_source.id)

        assert len(tables) == 1
        assert tables[0].identifier == "fake_table"

    async def test_unknown_data_source_raises_not_found(self) -> None:
        use_case = DiscoverDataSourceSchemaUseCase(
            data_source_repo=FakeDataSourceRepository(),
            cipher=FakeCredentialCipher(),
            connector_factory=FakeConnectorFactory(FakeConnector()),
        )

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(tenant_id=uuid4(), data_source_id=uuid4())
