"""Shared pytest fixtures for the Quantix API test suite."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

# Required settings must be present before any module imports
# `quantix_api.core.config` (which validates at import time via
# `get_settings()` being called eagerly in `main.py`).
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ.setdefault("POSTGRES_DB", "quantix_test")


@pytest.fixture
def client() -> Iterator[TestClient]:
    from quantix_api.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
