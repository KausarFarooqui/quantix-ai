"""FastAPI providers for stateless infrastructure services (password
hasher, token service, OAuth clients, audit logger).

Password hasher and token service are process-wide singletons pulled from
the container; the audit logger is request-scoped because it wraps a
request-scoped repository/session.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Path, status

from quantix_api.application.interfaces.agent_graph import AgentGraph
from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.application.interfaces.connector_factory import ConnectorFactory
from quantix_api.application.interfaces.credential_cipher import CredentialCipher
from quantix_api.application.interfaces.dataset_storage import DatasetStorage
from quantix_api.application.interfaces.file_storage import FileStorage
from quantix_api.application.interfaces.llm_client import LLMClient
from quantix_api.application.interfaces.oauth_provider import OAuthProviderClient
from quantix_api.application.interfaces.password_hasher import PasswordHasher
from quantix_api.application.interfaces.token_service import TokenService
from quantix_api.core.container import get_container
from quantix_api.domain.entities.oauth_account import OAuthProviderName
from quantix_api.infrastructure.logging.audit_logger import DatabaseAuditLogger
from quantix_api.interface.api.v1.dependencies.repositories import AuditLogRepo


def get_password_hasher() -> PasswordHasher:
    return get_container().password_hasher


def get_token_service() -> TokenService:
    return get_container().token_service


def get_audit_logger(audit_log_repo: AuditLogRepo) -> AuditLogger:
    return DatabaseAuditLogger(audit_log_repo)


def get_credential_cipher() -> CredentialCipher:
    return get_container().credential_cipher


def get_file_storage() -> FileStorage:
    return get_container().file_storage


def get_dataset_storage() -> DatasetStorage:
    return get_container().dataset_storage


def get_connector_factory() -> ConnectorFactory:
    return get_container().connector_factory


def get_llm_client() -> LLMClient:
    return get_container().llm_client


def get_agent_graph() -> AgentGraph:
    return get_container().agent_graph


def get_oauth_client(provider: Annotated[str, Path()]) -> OAuthProviderClient:
    try:
        provider_name = OAuthProviderName(provider)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown OAuth provider: {provider}"
        ) from exc

    client = get_container().oauth_clients.get(provider_name)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"OAuth provider '{provider}' is not configured on this server",
        )
    return client


PasswordHasherDep = Annotated[PasswordHasher, Depends(get_password_hasher)]
TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]
AuditLoggerDep = Annotated[AuditLogger, Depends(get_audit_logger)]
OAuthClientDep = Annotated[OAuthProviderClient, Depends(get_oauth_client)]
CredentialCipherDep = Annotated[CredentialCipher, Depends(get_credential_cipher)]
FileStorageDep = Annotated[FileStorage, Depends(get_file_storage)]
DatasetStorageDep = Annotated[DatasetStorage, Depends(get_dataset_storage)]
ConnectorFactoryDep = Annotated[ConnectorFactory, Depends(get_connector_factory)]
LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]
AgentGraphDep = Annotated[AgentGraph, Depends(get_agent_graph)]
