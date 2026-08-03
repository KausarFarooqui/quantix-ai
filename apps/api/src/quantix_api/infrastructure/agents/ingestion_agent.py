"""Data ingestion agent node — wraps milestone 3's connector use cases
rather than reasoning in text, since ingestion is an existing, tested
capability, not something an LLM should be asked to reimplement.

Deliberately scoped to *refreshing* the dataset already attached to a
conversation (via ``SyncDatasetUseCase.resync``), not accepting new data
source credentials typed into chat: connecting a brand-new source goes
through the dedicated ``POST /data-sources`` endpoint (see ADR-0003),
which is the only place secrets should ever be submitted. Extending this
agent to *choose* among a tenant's already-configured data sources by
name is a natural, safe follow-up — see ADR-0004.
"""

from __future__ import annotations

import time

from quantix_api.application.interfaces.agent_graph import (
    AgentRunContext,
    AgentRunResult,
    AgentState,
)
from quantix_api.domain.entities.agent_run import AgentRunStatus, AgentType
from quantix_api.domain.entities.dataset import DatasetStatus

_NO_DATASET_MESSAGE = (
    "No dataset is attached to this conversation yet. Create a data source and sync a dataset "
    "via the Data Sources page (or the /data-sources API), then start a conversation scoped to "
    "it — for security, this agent does not accept database credentials typed in chat."
)


class DataIngestionAgentNode:
    async def run(self, *, state: AgentState, context: AgentRunContext) -> AgentRunResult:
        started = time.monotonic()

        if context.dataset is None:
            return AgentRunResult(
                agent_type=AgentType.DATA_INGESTION,
                status=AgentRunStatus.SUCCEEDED,
                output_summary=_NO_DATASET_MESSAGE,
                latency_ms=int((time.monotonic() - started) * 1000),
            )

        try:
            refreshed = await context.sync_dataset_use_case.resync(
                tenant_id=context.tenant_id,
                dataset_id=context.dataset.id,
                actor_user_id=context.actor_user_id,
            )
        except Exception as exc:  # noqa: BLE001 — converted to a FAILED AgentRunResult
            return AgentRunResult(
                agent_type=AgentType.DATA_INGESTION,
                status=AgentRunStatus.FAILED,
                latency_ms=int((time.monotonic() - started) * 1000),
                error_message=str(exc),
            )

        if refreshed.status is DatasetStatus.READY:
            summary = (
                f"Refreshed dataset '{refreshed.name}' from its source — now {refreshed.row_count} "
                f"rows (last synced {refreshed.last_synced_at})."
            )
        else:
            summary = (
                f"Attempted to refresh dataset '{refreshed.name}' but it ended up in status "
                f"'{refreshed.status.value}': {refreshed.status_message or 'no further detail available'}."
            )

        return AgentRunResult(
            agent_type=AgentType.DATA_INGESTION,
            status=AgentRunStatus.SUCCEEDED if refreshed.status is DatasetStatus.READY else AgentRunStatus.FAILED,
            output_summary=summary,
            latency_ms=int((time.monotonic() - started) * 1000),
            error_message=None if refreshed.status is DatasetStatus.READY else refreshed.status_message,
        )
