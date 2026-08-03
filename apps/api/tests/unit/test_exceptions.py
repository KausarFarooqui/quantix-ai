"""Unit tests for domain exception → HTTP status mapping."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.interface.api.exception_handlers import register_exception_handlers


def test_entity_not_found_maps_to_404() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise EntityNotFoundError("User", uuid4())

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["error_type"] == "EntityNotFoundError"
