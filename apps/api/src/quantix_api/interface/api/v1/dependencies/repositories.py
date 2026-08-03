"""FastAPI providers for repository instances — one per request, bound to
the request-scoped ``AsyncSession`` from ``dependencies.db``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from quantix_api.domain.repositories.agent_run_repository import AgentRunRepository
from quantix_api.domain.repositories.audit_log_repository import AuditLogRepository
from quantix_api.domain.repositories.conversation_repository import ConversationRepository
from quantix_api.domain.repositories.data_source_repository import DataSourceRepository
from quantix_api.domain.repositories.dataset_repository import DatasetRepository
from quantix_api.domain.repositories.message_repository import MessageRepository
from quantix_api.domain.repositories.oauth_account_repository import OAuthAccountRepository
from quantix_api.domain.repositories.refresh_token_repository import RefreshTokenRepository
from quantix_api.domain.repositories.tenant_repository import TenantRepository
from quantix_api.domain.repositories.user_repository import UserRepository
from quantix_api.infrastructure.database.repositories.agent_run_repository import (
    SqlAlchemyAgentRunRepository,
)
from quantix_api.infrastructure.database.repositories.audit_log_repository import (
    SqlAlchemyAuditLogRepository,
)
from quantix_api.infrastructure.database.repositories.conversation_repository import (
    SqlAlchemyConversationRepository,
)
from quantix_api.infrastructure.database.repositories.data_source_repository import (
    SqlAlchemyDataSourceRepository,
)
from quantix_api.infrastructure.database.repositories.dataset_repository import (
    SqlAlchemyDatasetRepository,
)
from quantix_api.infrastructure.database.repositories.message_repository import (
    SqlAlchemyMessageRepository,
)
from quantix_api.infrastructure.database.repositories.oauth_account_repository import (
    SqlAlchemyOAuthAccountRepository,
)
from quantix_api.infrastructure.database.repositories.refresh_token_repository import (
    SqlAlchemyRefreshTokenRepository,
)
from quantix_api.infrastructure.database.repositories.tenant_repository import (
    SqlAlchemyTenantRepository,
)
from quantix_api.infrastructure.database.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from quantix_api.interface.api.v1.dependencies.db import DbSession


def get_user_repository(session: DbSession) -> UserRepository:
    return SqlAlchemyUserRepository(session)


def get_tenant_repository(session: DbSession) -> TenantRepository:
    return SqlAlchemyTenantRepository(session)


def get_refresh_token_repository(session: DbSession) -> RefreshTokenRepository:
    return SqlAlchemyRefreshTokenRepository(session)


def get_oauth_account_repository(session: DbSession) -> OAuthAccountRepository:
    return SqlAlchemyOAuthAccountRepository(session)


def get_audit_log_repository(session: DbSession) -> AuditLogRepository:
    return SqlAlchemyAuditLogRepository(session)


def get_data_source_repository(session: DbSession) -> DataSourceRepository:
    return SqlAlchemyDataSourceRepository(session)


def get_dataset_repository(session: DbSession) -> DatasetRepository:
    return SqlAlchemyDatasetRepository(session)


def get_conversation_repository(session: DbSession) -> ConversationRepository:
    return SqlAlchemyConversationRepository(session)


def get_message_repository(session: DbSession) -> MessageRepository:
    return SqlAlchemyMessageRepository(session)


def get_agent_run_repository(session: DbSession) -> AgentRunRepository:
    return SqlAlchemyAgentRunRepository(session)


UserRepo = Annotated[UserRepository, Depends(get_user_repository)]
TenantRepo = Annotated[TenantRepository, Depends(get_tenant_repository)]
RefreshTokenRepo = Annotated[RefreshTokenRepository, Depends(get_refresh_token_repository)]
OAuthAccountRepo = Annotated[OAuthAccountRepository, Depends(get_oauth_account_repository)]
AuditLogRepo = Annotated[AuditLogRepository, Depends(get_audit_log_repository)]
DataSourceRepo = Annotated[DataSourceRepository, Depends(get_data_source_repository)]
DatasetRepo = Annotated[DatasetRepository, Depends(get_dataset_repository)]
ConversationRepo = Annotated[ConversationRepository, Depends(get_conversation_repository)]
MessageRepo = Annotated[MessageRepository, Depends(get_message_repository)]
AgentRunRepo = Annotated[AgentRunRepository, Depends(get_agent_run_repository)]
