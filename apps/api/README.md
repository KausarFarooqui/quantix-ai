# Quantix API

FastAPI backend for Quantix AI, built with Clean Architecture layering
(`domain` → `application` → `infrastructure` → `interface`). See the
[repository README](../../README.md) and
[architecture doc](../../docs/ARCHITECTURE.md) for the full picture.

## Local development

```bash
# From apps/api
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e ".[dev]"

cp .env.example .env   # then edit SECRET_KEY at minimum

# Run the API
uvicorn quantix_api.main:app --reload

# Run tests
pytest

# Lint / type-check
ruff check .
mypy src
```

## Authentication

Email/password plus Google/GitHub/Microsoft OAuth — see
[ADR-0002](../../docs/adr/0002-authentication-and-multi-tenancy.md) for
the design. Endpoints live under `/api/v1/auth`:
`register`, `login`, `refresh`, `logout`, `me`, and
`oauth/{provider}/authorize` / `oauth/{provider}/callback`.

To enable a given OAuth provider, set its client ID/secret in `.env`
(`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`, etc.) and register
`{API_PUBLIC_URL}/api/v1/auth/oauth/{provider}/callback` as the redirect
URI in that provider's OAuth app console. Providers without credentials
configured return `501 Not Implemented` rather than erroring at startup.

## Database migrations

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## Layout

```
src/quantix_api/
  domain/          # Entities, value objects, repository interfaces, domain exceptions — no framework imports.
  application/      # Use cases / application services orchestrating domain logic.
  infrastructure/   # SQLAlchemy models & repos, Celery, cache, logging, security — implements domain ports.
  interface/         # FastAPI routes, Pydantic schemas, dependency wiring — the HTTP boundary.
  core/             # Settings, DI container, cross-cutting config.
```
