"""Unit tests for application settings."""

from __future__ import annotations

from quantix_api.core.config import Environment, Settings


def test_database_url_uses_asyncpg_driver() -> None:
    settings = Settings(
        secret_key="unit-test-secret",  # type: ignore[arg-type]
        postgres_host="db.internal",
        postgres_port=5432,
        postgres_user="quantix",
        postgres_password="pw",  # type: ignore[arg-type]
        postgres_db="quantix",
    )

    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert "db.internal:5432/quantix" in settings.database_url


def test_redis_url_format() -> None:
    settings = Settings(
        secret_key="unit-test-secret",  # type: ignore[arg-type]
        redis_host="cache.internal",
        redis_port=6379,
        redis_db=2,
    )

    assert settings.redis_url == "redis://cache.internal:6379/2"


def test_is_production_flag() -> None:
    dev_settings = Settings(
        secret_key="unit-test-secret",  # type: ignore[arg-type]
        environment=Environment.DEVELOPMENT,
    )
    prod_settings = Settings(
        secret_key="unit-test-secret",  # type: ignore[arg-type]
        environment=Environment.PRODUCTION,
    )

    assert dev_settings.is_production is False
    assert prod_settings.is_production is True


def test_secret_key_is_not_exposed_in_repr() -> None:
    settings = Settings(secret_key="super-secret-value")  # type: ignore[arg-type]

    assert "super-secret-value" not in repr(settings.secret_key)
    assert settings.secret_key.get_secret_value() == "super-secret-value"
