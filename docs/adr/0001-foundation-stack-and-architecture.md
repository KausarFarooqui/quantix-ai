# ADR-0001: Foundation stack and architectural style

- **Status:** Accepted
- **Date:** 2026-08-02
- **Deciders:** Quantix AI engineering

## Context

Milestone 1 needs to establish the base every later milestone (auth,
connectors, AI agents, ML pipelines, reporting) builds on. The product
vision — an AI-native competitor to Power BI/Tableau/ThoughtSpot/Hex —
implies: multi-tenant SaaS from day one, heavy async I/O (LLM calls, long
agent chains, large dataset processing), a data layer that must support
both transactional and analytical workloads, and a frontend capable of
dense, interactive data visualization at a "premium SaaS" polish bar.

## Decision

**Backend:** FastAPI + Python 3.13, SQLAlchemy 2 (async) + Alembic,
Pydantic v2, Celery + Redis, organized as **Clean Architecture**
(`domain` / `application` / `infrastructure` / `interface`).

**Frontend:** Next.js 15 (App Router) + React 19 + TypeScript, Tailwind +
shadcn/ui, TanStack Query for server state, Zustand for client UI state,
React Hook Form + Zod for forms, AG Grid + Apache ECharts for data-dense
views.

**Data stores:** PostgreSQL (system of record), DuckDB (embedded OLAP for
ad-hoc analytical queries), Redis (cache + Celery transport), Qdrant
(vector search for RAG).

**Monorepo layout:** `apps/api` + `apps/web` as independently deployable
services sharing one repo, one CI pipeline, one docker-compose stack.

## Alternatives considered

- **Django + DRF instead of FastAPI** — rejected: FastAPI's native
  async support and Pydantic-first design fit an I/O-heavy, LLM-calling
  backend better; Django's batteries (admin, ORM migrations) are less
  valuable here than async performance and OpenAPI-first contracts.
- **Single-package "fat" backend (no layering) instead of Clean
  Architecture** — rejected: with 12 planned AI agents, ML training
  pipelines, and multiple data connectors converging on the same domain
  models, an unstructured backend becomes unmaintainable quickly. The
  layering cost (more files, explicit ports) is paid once and amortized
  over every subsequent milestone.
- **Prisma/Drizzle-style TS backend (Node monolith) instead of a
  separate Python API** — rejected: the ML/AI surface (scikit-learn,
  SHAP, LangGraph, pandas) is Python-native; splitting frontend and
  backend by language lets each side use its ecosystem's strengths
  instead of forcing Python ML code behind a second bridge process.
- **MongoDB instead of PostgreSQL as system of record** — rejected:
  the domain is heavily relational (tenants → users → connectors →
  dashboards → models, with RBAC and audit trails), and Postgres's JSONB
  columns cover the document-shaped data (e.g. raw connector configs)
  without giving up transactional guarantees elsewhere.
- **Turborepo/Nx workspace tooling** — deferred, not rejected: two apps
  don't yet justify the tooling overhead; revisit once `packages/shared`
  (generated API types, shared UI primitives) materializes.

## Consequences

**Positive:** domain logic is unit-testable without a database; swapping
infrastructure (e.g. a different vector DB) touches one layer; new
engineers can find "where does X live" by the dependency rule alone;
async-first backend scales to concurrent LLM/agent calls without a
separate async framework migration later.

**Negative:** more ceremony for simple CRUD (an entity, a model, a
repository, a schema, a route — five files instead of one); Python 3.13 +
SQLAlchemy 2 async is a young combination, so some third-party libraries
may lag in async support and need workarounds; running two languages
(Python + TypeScript) means two dependency ecosystems, two linters, two
CI jobs to maintain.

**Follow-ups tracked for later milestones:** row-level tenant isolation
enforcement (ADR pending, milestone 2), `packages/shared` for
OpenAPI-generated TS types once the API surface stabilizes, evaluation of
Turborepo once a third app or shared package appears.
