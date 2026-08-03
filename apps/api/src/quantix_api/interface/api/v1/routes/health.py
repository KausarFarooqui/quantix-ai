"""Liveness/readiness endpoints.

``/health/live`` — process is up (used by container orchestrators for
restart decisions). ``/health/ready`` — process can serve traffic, i.e. its
dependencies (database) are reachable (used for load-balancer routing).
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from quantix_api import __version__
from quantix_api.core.config import get_settings
from quantix_api.core.container import get_container
from quantix_api.core.logging import get_logger
from quantix_api.interface.api.v1.schemas.health import ComponentStatus, HealthResponse

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger(__name__)


@router.get("/live", response_model=HealthResponse, summary="Liveness probe")
async def liveness() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=settings.environment.value,
        components=[],
    )


@router.get("/ready", response_model=HealthResponse, summary="Readiness probe")
async def readiness() -> HealthResponse:
    settings = get_settings()
    container = get_container()
    components: list[ComponentStatus] = []

    try:
        async with container.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        components.append(ComponentStatus(name="postgres", healthy=True))
    except Exception as exc:  # noqa: BLE001 — deliberately broad for a probe
        logger.warning("readiness_check_failed", component="postgres", error=str(exc))
        components.append(ComponentStatus(name="postgres", healthy=False, detail=str(exc)))

    overall_status = "ok" if all(c.healthy for c in components) else "degraded"
    return HealthResponse(
        status=overall_status,
        version=__version__,
        environment=settings.environment.value,
        components=components,
    )
