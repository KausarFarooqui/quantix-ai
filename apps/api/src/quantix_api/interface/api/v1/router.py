"""Aggregate router for API v1 — mount all feature routers here."""

from __future__ import annotations

from fastapi import APIRouter

from quantix_api.interface.api.v1.routes import (
    auth,
    conversations,
    data_sources,
    datasets,
    forecasts,
    health,
    oauth,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(oauth.router)
api_router.include_router(data_sources.router)
api_router.include_router(datasets.router)
api_router.include_router(forecasts.router)
api_router.include_router(conversations.router)
