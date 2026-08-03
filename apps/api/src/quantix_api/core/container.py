"""Composition root — the single place infrastructure is wired together.

FastAPI's dependency-injection system doubles as our DI container: this
module owns construction of the engine/session-factory singletons and
exposes narrow ``Depends``-compatible providers. No other module should
call ``create_async_engine`` directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from quantix_api.application.interfaces.agent_graph import AgentGraph
from quantix_api.application.interfaces.connector_factory import ConnectorFactory
from quantix_api.application.interfaces.credential_cipher import CredentialCipher
from quantix_api.application.interfaces.dataset_storage import DatasetStorage
from quantix_api.application.interfaces.file_storage import FileStorage
from quantix_api.application.interfaces.llm_client import LLMClient
from quantix_api.application.interfaces.oauth_provider import OAuthProviderClient
from quantix_api.application.interfaces.password_hasher import PasswordHasher
from quantix_api.application.interfaces.token_service import TokenService
from quantix_api.core.config import Settings, get_settings
from quantix_api.domain.entities.oauth_account import OAuthProviderName
from quantix_api.infrastructure.agents.graph import LangGraphAgentGraph, build_agent_graph
from quantix_api.infrastructure.connectors.registry import ConnectorRegistry
from quantix_api.infrastructure.database.session import create_engine, create_session_factory
from quantix_api.infrastructure.llm.anthropic_client import AnthropicLLMClient
from quantix_api.infrastructure.security.credential_cipher import FernetCredentialCipher
from quantix_api.infrastructure.security.jwt_service import JWTTokenService
from quantix_api.infrastructure.security.oauth import (
    GitHubOAuthClient,
    GoogleOAuthClient,
    MicrosoftOAuthClient,
)
from quantix_api.infrastructure.security.password_hasher import Argon2PasswordHasher
from quantix_api.infrastructure.storage.duckdb_dataset_storage import DuckDBDatasetStorage
from quantix_api.infrastructure.storage.file_storage import LocalFileStorage


def _build_oauth_clients(settings: Settings) -> dict[OAuthProviderName, OAuthProviderClient]:
    """Only register providers whose credentials are actually configured —
    unconfigured providers are simply absent from the map rather than
    present-but-broken, so the auth routes can 404 cleanly on them.
    """
    clients: dict[OAuthProviderName, OAuthProviderClient] = {}

    if settings.google_client_id and settings.google_client_secret:
        clients[OAuthProviderName.GOOGLE] = GoogleOAuthClient(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret.get_secret_value(),
        )
    if settings.github_client_id and settings.github_client_secret:
        clients[OAuthProviderName.GITHUB] = GitHubOAuthClient(
            client_id=settings.github_client_id,
            client_secret=settings.github_client_secret.get_secret_value(),
        )
    if settings.microsoft_client_id and settings.microsoft_client_secret:
        clients[OAuthProviderName.MICROSOFT] = MicrosoftOAuthClient(
            client_id=settings.microsoft_client_id,
            client_secret=settings.microsoft_client_secret.get_secret_value(),
        )
    return clients


@dataclass(slots=True)
class Container:
    """Process-wide singleton holder for expensive infrastructure objects."""

    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    password_hasher: PasswordHasher
    token_service: TokenService
    credential_cipher: CredentialCipher
    file_storage: FileStorage
    dataset_storage: DatasetStorage
    connector_factory: ConnectorFactory
    llm_client: LLMClient
    agent_graph: AgentGraph
    oauth_clients: dict[OAuthProviderName, OAuthProviderClient] = field(default_factory=dict)

    async def shutdown(self) -> None:
        """Dispose of pooled connections on application shutdown."""
        await self.engine.dispose()


@lru_cache
def get_container() -> Container:
    """Build (once) and return the process-wide DI container."""
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    token_service = JWTTokenService(
        secret_key=settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
        access_token_expire_minutes=settings.access_token_expire_minutes,
    )
    file_storage = LocalFileStorage(base_dir=settings.file_storage_dir)

    llm_client = AnthropicLLMClient(
        api_key=settings.anthropic_api_key.get_secret_value(), model=settings.agent_llm_model
    )
    # Compiled once here, not per-request: the graph's node closures only
    # capture this stateless LLM client. Request-scoped dependencies (a
    # dataset's repository, storage, other use cases) are threaded through
    # at invoke time via AgentRunContext — see infrastructure.agents.graph.
    compiled_graph = build_agent_graph(
        llm_client=llm_client, max_tool_iterations=settings.agent_max_tool_iterations
    )
    agent_graph = LangGraphAgentGraph(
        compiled_graph=compiled_graph, max_iterations=settings.agent_max_supervisor_iterations
    )

    return Container(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        password_hasher=Argon2PasswordHasher(),
        token_service=token_service,
        credential_cipher=FernetCredentialCipher(
            encryption_key=settings.credential_encryption_key.get_secret_value()
        ),
        file_storage=file_storage,
        dataset_storage=DuckDBDatasetStorage(base_dir=settings.dataset_storage_dir),
        connector_factory=ConnectorRegistry(file_storage=file_storage),
        llm_client=llm_client,
        agent_graph=agent_graph,
        oauth_clients=_build_oauth_clients(settings),
    )
