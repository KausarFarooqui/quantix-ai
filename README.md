# Quantix AI

AI-powered analytics platform: connect data sources, clean and transform
data automatically, analyze it in natural language, generate dashboards,
train predictive models, forecast trends, detect anomalies, and produce
executive reports.

This repository is being built incrementally, milestone by milestone. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the system design and
[docs/adr/](docs/adr/) for the reasoning behind major technical decisions.

## Milestone status

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Foundation & scaffolding | ✅ Done |
| 2 | Authentication & multi-tenancy (backend) | ✅ Done |
| 3 | Data connector layer (backend) | ✅ Done |
| 4 | AI agent core — LangGraph orchestration (backend) | ✅ Done |
| 5 | Frontend authentication & app shell | ✅ Done |
| 6 | Frontend data source & dataset management UI | ✅ Done |
| 7 | Frontend chat interface | ✅ Done |
| 8+ | ML pipelines, reporting, dashboards, remaining agents | ⬜ Not started |

Milestone 2 shipped email/password auth, Google/GitHub/Microsoft OAuth,
JWT + revocable refresh tokens, RBAC, and audit logging on the backend —
see [ADR-0002](docs/adr/0002-authentication-and-multi-tenancy.md) for the
design and known follow-ups (invitations, OAuth account linking, a
"find my workspaces" lookup).

Milestone 5 gave the frontend its first real pages: `/login`, `/register`,
the OAuth callback, and a protected app shell — see
[ADR-0005](docs/adr/0005-frontend-auth-and-session.md) for the session
storage and route-protection design.

Milestone 6 shipped `/data-sources` (add/test/discover/delete a live
connection) and `/datasets` (upload a file, pull a table from a data
source, preview/resync/delete) — see
[ADR-0006](docs/adr/0006-frontend-connector-and-dataset-ui.md) for the
dynamic per-source-type config form and the `ag-grid` preview.

Milestone 7 shipped `/chat` — start a conversation (optionally scoped to a
dataset), send messages, and watch the multi-agent supervisor route each
turn to the right specialist. The backend runs each turn synchronously
(no streaming yet), so the composer optimistically shows the user's own
message right away and an "agent is working" state while it waits; a
sidebar panel lists which specialists ran each turn. See
[ADR-0007](docs/adr/0007-frontend-chat-interface.md) for the full design,
including why streaming was deliberately left out of this milestone.

## Repository structure

```
quantix-ai/
  apps/
    api/            # FastAPI backend — Clean Architecture (domain/application/infrastructure/interface)
    web/            # Next.js 15 / React 19 frontend
  infra/            # Shared infrastructure assets (reserved for k8s manifests, terraform, etc.)
  docs/
    ARCHITECTURE.md
    adr/            # Architecture Decision Records
  docker-compose.yml
  .github/workflows/ci.yml
```

## Quickstart

### Option A — Docker Compose (fastest path to a running stack)

```bash
cp apps/api/.env.example apps/api/.env      # edit SECRET_KEY at minimum
cp apps/web/.env.example apps/web/.env.local

docker compose up --build
```

- API: http://localhost:8000/api/v1/docs (Swagger UI)
- Web: http://localhost:3000
- Postgres: localhost:5432 · Redis: localhost:6379 · Qdrant: localhost:6333

### Option B — Run services natively

See [apps/api/README.md](apps/api/README.md) and
[apps/web/README.md](apps/web/README.md) for per-service setup, or:

```bash
# Backend
cd apps/api
uv venv --python 3.13 && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env
uvicorn quantix_api.main:app --reload

# Frontend (separate terminal)
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```

## Testing

```bash
# Backend — from apps/api
pytest                    # unit + API tests, ≥90% coverage enforced

# Frontend — from apps/web
npm run test               # Vitest unit/component tests
npm run typecheck
npm run lint
```

CI runs both suites plus a Docker build sanity check on every push/PR — see
[.github/workflows/ci.yml](.github/workflows/ci.yml).

## Core principles

Clean Architecture, Domain-Driven Design, SOLID, Repository Pattern,
Dependency Injection, feature-based modules, strong typing end-to-end, and
security/accessibility/performance treated as first-class requirements
rather than afterthoughts. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
for how these show up in the codebase.

## License

Proprietary — all rights reserved.
