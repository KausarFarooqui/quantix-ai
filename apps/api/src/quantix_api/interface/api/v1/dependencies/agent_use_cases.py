"""FastAPI providers assembling the conversation/agent use cases from
repositories + services, mirroring ``dependencies.connector_use_cases``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from quantix_api.application.use_cases.send_message import SendMessageUseCase
from quantix_api.application.use_cases.start_conversation import StartConversationUseCase
from quantix_api.core.config import get_settings
from quantix_api.interface.api.v1.dependencies.connector_use_cases import (
    DiscoverDataSourceSchemaUseCaseDep,
    SyncDatasetUseCaseDep,
)
from quantix_api.interface.api.v1.dependencies.repositories import (
    AgentRunRepo,
    ConversationRepo,
    DataSourceRepo,
    DatasetRepo,
    MessageRepo,
)
from quantix_api.interface.api.v1.dependencies.services import (
    AgentGraphDep,
    AuditLoggerDep,
    ConnectorFactoryDep,
    CredentialCipherDep,
    DatasetStorageDep,
)


def get_start_conversation_use_case(
    conversation_repo: ConversationRepo, dataset_repo: DatasetRepo, audit_logger: AuditLoggerDep
) -> StartConversationUseCase:
    return StartConversationUseCase(
        conversation_repo=conversation_repo, dataset_repo=dataset_repo, audit_logger=audit_logger
    )


def get_send_message_use_case(
    conversation_repo: ConversationRepo,
    message_repo: MessageRepo,
    agent_run_repo: AgentRunRepo,
    dataset_repo: DatasetRepo,
    dataset_storage: DatasetStorageDep,
    data_source_repo: DataSourceRepo,
    connector_factory: ConnectorFactoryDep,
    cipher: CredentialCipherDep,
    sync_dataset_use_case: SyncDatasetUseCaseDep,
    discover_use_case: DiscoverDataSourceSchemaUseCaseDep,
    agent_graph: AgentGraphDep,
    audit_logger: AuditLoggerDep,
) -> SendMessageUseCase:
    settings = get_settings()
    return SendMessageUseCase(
        conversation_repo=conversation_repo,
        message_repo=message_repo,
        agent_run_repo=agent_run_repo,
        dataset_repo=dataset_repo,
        dataset_storage=dataset_storage,
        data_source_repo=data_source_repo,
        connector_factory=connector_factory,
        cipher=cipher,
        sync_dataset_use_case=sync_dataset_use_case,
        discover_use_case=discover_use_case,
        agent_graph=agent_graph,
        audit_logger=audit_logger,
        max_iterations=settings.agent_max_supervisor_iterations,
    )


StartConversationUseCaseDep = Annotated[
    StartConversationUseCase, Depends(get_start_conversation_use_case)
]
SendMessageUseCaseDep = Annotated[SendMessageUseCase, Depends(get_send_message_use_case)]
