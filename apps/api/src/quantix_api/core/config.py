"""Application configuration.

Centralizes all runtime configuration behind a single, strongly-typed
``Settings`` object sourced from environment variables (and ``.env`` in
local development). No module outside ``core`` should read ``os.environ``
directly — this keeps configuration testable and swappable per environment.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Deployment environment discriminator."""

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Values are loaded from environment variables first, falling back to a
    local ``.env`` file when present. Field names map 1:1 to environment
    variable names (case-insensitive).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Core ---
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: str = "INFO"
    project_name: str = "Quantix AI"
    api_v1_prefix: str = "/api/v1"
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    frontend_url: str = "http://localhost:3000"
    # Publicly reachable base URL of *this* API — used to build OAuth
    # redirect_uris, which must point at the backend (the provider calls
    # them directly), not the frontend. Distinct from `frontend_url`
    # because they're typically different origins/subdomains in production.
    api_public_url: str = "http://localhost:8000"

    # --- Security ---
    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    # Deliberately separate from secret_key (which signs JWTs) — a
    # dedicated key for encrypting connector credentials at rest so the
    # two purposes can be rotated independently.
    credential_encryption_key: SecretStr = SecretStr("dev-only-credential-key-change-in-production")

    # --- Data connector storage ---
    # Local filesystem by default; a follow-up milestone should make this
    # pluggable (S3/GCS) via the same FileStorage/DatasetStorage ports.
    file_storage_dir: str = "./data/uploads"
    dataset_storage_dir: str = "./data/datasets"

    # --- AI agents ---
    anthropic_api_key: SecretStr = SecretStr("")
    agent_llm_model: str = "claude-sonnet-5"
    agent_max_tokens: int = 4096
    # Supervisor routing hops per conversation turn — a circuit breaker
    # against a misbehaving routing loop burning LLM spend indefinitely.
    agent_max_supervisor_iterations: int = 6
    # Tool-call round-trips within a single specialized agent's own turn.
    agent_max_tool_iterations: int = 5

    # --- PostgreSQL ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "quantix"
    postgres_password: SecretStr = SecretStr("quantix_dev_password")
    postgres_db: str = "quantix"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # --- Redis ---
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # --- Celery ---
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # --- Qdrant ---
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # --- OAuth ---
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    github_client_id: str | None = None
    github_client_secret: SecretStr | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: SecretStr | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async SQLAlchemy connection string (asyncpg driver)."""
        dsn = PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            path=self.postgres_db,
        )
        return str(dsn)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        """Redis connection string used for caching."""
        dsn = RedisDsn.build(
            scheme="redis",
            host=self.redis_host,
            port=self.redis_port,
            path=str(self.redis_db),
        )
        return str(dsn)

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @property
    def is_test(self) -> bool:
        return self.environment is Environment.TEST


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached ``Settings`` instance.

    Cached via ``lru_cache`` so environment parsing happens once per
    process; tests override this via FastAPI's dependency-override
    mechanism rather than mutating the cache.
    """
    return Settings()  # type: ignore[call-arg]
