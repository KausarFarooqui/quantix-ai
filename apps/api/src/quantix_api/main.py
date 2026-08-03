"""Application entry point — FastAPI app factory.

Run locally with: ``uvicorn quantix_api.main:app --reload``
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quantix_api import __version__
from quantix_api.core.config import get_settings
from quantix_api.core.container import get_container
from quantix_api.core.logging import configure_logging, get_logger
from quantix_api.infrastructure.logging.middleware import RequestContextMiddleware
from quantix_api.interface.api.exception_handlers import register_exception_handlers
from quantix_api.interface.api.v1.router import api_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup/shutdown hooks — dispose the DB pool cleanly on exit."""
    settings = get_settings()
    logger.info("application_startup", environment=settings.environment.value)
    yield
    container = get_container()
    await container.shutdown()
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application instance."""
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.project_name,
        version=__version__,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=f"{settings.api_v1_prefix}/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
