"""Unit tests for DataIngestionAgentNode."""

from __future__ import annotations

from uuid import uuid4

from _agent_fakes import FakeDatasetStorage, FakeSyncDatasetUseCase

from quantix_api.application.interfaces.agent_graph import AgentRunContext, AgentState, AgentTurn
from quantix_api.domain.entities.agent_run import AgentRunStatus
from quantix_api.domain.entities.dataset import Dataset, DatasetStatus
from quantix_api.infrastructure.agents.ingestion_agent import DataIngestionAgentNode


def _state() -> AgentState:
    return AgentState(
        conversation_id=uuid4(), tenant_id=uuid4(), history=[AgentTurn(role="user", content="refresh my data")]
    )


class TestDataIngestionAgentNode:
    async def test_no_dataset_attached_reports_that_clearly(self) -> None:
        context = AgentRunContext(
            tenant_id=uuid4(),
            actor_user_id=uuid4(),
            dataset=None,
            dataset_repo=None,
            dataset_storage=FakeDatasetStorage(),
            data_source_repo=None,
            connector_factory=None,
            cipher=None,
            sync_dataset_use_case=FakeSyncDatasetUseCase(),
            discover_use_case=None,
        )
        node = DataIngestionAgentNode()

        result = await node.run(state=_state(), context=context)

        assert result.status is AgentRunStatus.SUCCEEDED
        assert "No dataset is attached" in result.output_summary

    async def test_resyncs_the_attached_dataset(self) -> None:
        dataset = Dataset(tenant_id=uuid4(), data_source_id=uuid4(), name="orders", table_identifier="orders")
        refreshed = Dataset(
            id=dataset.id,
            tenant_id=dataset.tenant_id,
            data_source_id=dataset.data_source_id,
            name="orders",
            table_identifier="orders",
            status=DatasetStatus.READY,
            row_count=500,
        )
        sync_use_case = FakeSyncDatasetUseCase(resync_result=refreshed)
        actor_id = uuid4()
        context = AgentRunContext(
            tenant_id=dataset.tenant_id,
            actor_user_id=actor_id,
            dataset=dataset,
            dataset_repo=None,
            dataset_storage=FakeDatasetStorage(),
            data_source_repo=None,
            connector_factory=None,
            cipher=None,
            sync_dataset_use_case=sync_use_case,
            discover_use_case=None,
        )
        node = DataIngestionAgentNode()

        result = await node.run(state=_state(), context=context)

        assert result.status is AgentRunStatus.SUCCEEDED
        assert "500 rows" in result.output_summary
        assert sync_use_case.resync_calls == [
            {"tenant_id": dataset.tenant_id, "dataset_id": dataset.id, "actor_user_id": actor_id}
        ]

    async def test_resync_failure_is_a_failed_result(self) -> None:
        dataset = Dataset(tenant_id=uuid4(), data_source_id=uuid4(), name="orders", table_identifier="orders")
        sync_use_case = FakeSyncDatasetUseCase(raises=RuntimeError("connection refused"))
        context = AgentRunContext(
            tenant_id=dataset.tenant_id,
            actor_user_id=uuid4(),
            dataset=dataset,
            dataset_repo=None,
            dataset_storage=FakeDatasetStorage(),
            data_source_repo=None,
            connector_factory=None,
            cipher=None,
            sync_dataset_use_case=sync_use_case,
            discover_use_case=None,
        )
        node = DataIngestionAgentNode()

        result = await node.run(state=_state(), context=context)

        assert result.status is AgentRunStatus.FAILED
        assert "connection refused" in result.error_message
