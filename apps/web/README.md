# Quantix Web

Next.js 15 / React 19 frontend for Quantix AI.

## Local development

```bash
# From apps/web
npm install
cp .env.example .env.local

npm run dev        # http://localhost:3000
npm run test        # Vitest unit/component tests
npm run lint
npm run typecheck
```

## Structure

```
src/
  app/            # Next.js App Router routes, layouts, providers.
    (auth)/       # /login, /register
    auth/callback/  # /auth/callback — OAuth redirect target
    (app)/        # Protected app shell (/home, /data-sources, /datasets, /chat, ...)
  components/ui/  # shadcn/ui-style primitives (button, input, card, etc.).
  features/       # Feature-based modules (auth/, connectors/, dashboards/, chat/, ...).
  lib/            # API client (apiFetch/authFetch), utilities, shared config.
  stores/         # Zustand stores — ui-store.ts (client-only UI state), auth-store.ts (session state).
  hooks/          # Shared React hooks.
  types/          # Shared TypeScript types (mirrors backend schemas).
  styles/         # Global CSS, Tailwind theme tokens.
```

State management split: **TanStack Query** owns all server/remote data
(fetching, caching, invalidation); **Zustand** owns ephemeral client-only UI
state (sidebar collapse, command palette open/closed) — with one documented
exception, `auth-store.ts` (see
[ADR-0005](../../docs/adr/0005-frontend-auth-and-session.md)). Don't mix
Query and UI-state Zustand stores otherwise.

## Auth

`/login` and `/register` call the backend directly; a successful OAuth
sign-in redirects back to `/auth/callback`, which reads the token pair out
of the URL fragment. Everything under `app/(app)/` requires a session —
the layout redirects to `/login` if there isn't one. See
[ADR-0005](../../docs/adr/0005-frontend-auth-and-session.md) for the full
design.

## Data sources & datasets

`/data-sources` connects a live source (Postgres, MySQL, SQL Server,
SQLite, Snowflake, BigQuery, Google Sheets) and pulls tables from it into
datasets; `/datasets` covers file uploads plus previewing/resyncing/
deleting what's already there. The connection-config form
(`/data-sources/new`) renders a different field set per source type from
`features/connectors/source-type-fields.ts` — see
[ADR-0006](../../docs/adr/0006-frontend-connector-and-dataset-ui.md) for
why that form doesn't follow the `react-hook-form` + `zod` pattern every
other form in this app uses.

## Chat

`/chat` lists conversations, `/chat/new` starts one (optionally scoped to
a ready dataset), and `/chat/[id]` is the thread: a composer, the message
list, and a sidebar showing which specialist agents ran that turn. The
backend runs a whole turn synchronously and can take tens of seconds — the
composer inserts the user's own message optimistically and shows a pending
state rather than a blank thread while it waits. See
[ADR-0007](../../docs/adr/0007-frontend-chat-interface.md) for why there's
no streaming client yet and how the optimistic-update/rollback works.
