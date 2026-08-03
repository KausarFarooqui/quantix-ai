"""Pydantic schemas for the health-check endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ComponentStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    healthy: bool
    detail: str | None = None


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    version: str
    environment: str
    components: list[ComponentStatus]
