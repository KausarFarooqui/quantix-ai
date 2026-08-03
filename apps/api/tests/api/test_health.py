"""API tests for the health-check endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_liveness_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"
    assert "version" in body


def test_liveness_response_includes_request_id_header(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert "X-Request-ID" in response.headers
