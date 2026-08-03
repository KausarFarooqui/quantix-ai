"""Translate domain exceptions into HTTP responses.

Registered once on the FastAPI app in ``main.create_app``. Keeps
``raise EntityNotFoundError(...)`` usable from application/use-case code
without any of it knowing about HTTP status codes.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from quantix_api.core.logging import get_logger
from quantix_api.domain.exceptions.auth import (
    InactiveUserError,
    InvalidCredentialsError,
    InvalidOAuthStateError,
    InvalidRefreshTokenError,
    OAuthProviderError,
    RefreshTokenReuseError,
)
from quantix_api.domain.exceptions.base import (
    AuthorizationError,
    DomainError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    TenantSuspendedError,
)
from quantix_api.domain.exceptions.agents import (
    AgentError,
    AgentExecutionError,
    AgentIterationLimitExceededError,
    ConversationNotActiveError,
    LLMProviderError,
    UnknownAgentTypeError,
)
from quantix_api.domain.exceptions.connectors import (
    ConnectionTestFailedError,
    ConnectorError,
    DatasetNotReadyError,
    ExtractionError,
    SchemaDiscoveryError,
    UnsupportedFileFormatError,
    UnsupportedSourceTypeError,
)

logger = get_logger(__name__)

_STATUS_MAP: dict[type[DomainError], int] = {
    EntityNotFoundError: status.HTTP_404_NOT_FOUND,
    EntityAlreadyExistsError: status.HTTP_409_CONFLICT,
    AuthorizationError: status.HTTP_403_FORBIDDEN,
    TenantSuspendedError: status.HTTP_423_LOCKED,
    InvalidCredentialsError: status.HTTP_401_UNAUTHORIZED,
    InactiveUserError: status.HTTP_403_FORBIDDEN,
    InvalidRefreshTokenError: status.HTTP_401_UNAUTHORIZED,
    RefreshTokenReuseError: status.HTTP_401_UNAUTHORIZED,
    InvalidOAuthStateError: status.HTTP_400_BAD_REQUEST,
    OAuthProviderError: status.HTTP_502_BAD_GATEWAY,
    UnsupportedSourceTypeError: status.HTTP_400_BAD_REQUEST,
    UnsupportedFileFormatError: status.HTTP_400_BAD_REQUEST,
    ConnectionTestFailedError: status.HTTP_502_BAD_GATEWAY,
    SchemaDiscoveryError: status.HTTP_502_BAD_GATEWAY,
    ConnectorError: status.HTTP_502_BAD_GATEWAY,
    DatasetNotReadyError: status.HTTP_409_CONFLICT,
    ConversationNotActiveError: status.HTTP_409_CONFLICT,
    UnknownAgentTypeError: status.HTTP_400_BAD_REQUEST,
    AgentExecutionError: status.HTTP_502_BAD_GATEWAY,
    LLMProviderError: status.HTTP_502_BAD_GATEWAY,
    AgentIterationLimitExceededError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    AgentError: status.HTTP_502_BAD_GATEWAY,
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        status_code = _STATUS_MAP.get(type(exc), status.HTTP_400_BAD_REQUEST)
        if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            logger.error("domain_error", error=str(exc), path=request.url.path)
        else:
            logger.info("domain_error", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=status_code,
            content={"detail": str(exc), "error_type": type(exc).__name__},
        )
