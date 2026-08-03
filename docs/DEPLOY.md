# Deploying Quantix AI

This covers deploying what's actually been built so far (milestones 1-7:
auth, data connectors, the chat/agent system) to a public URL on
[Render](https://render.com), using the [`render.yaml`](../render.yaml)
Blueprint at the repo root. It's one option among several (Railway, Fly.io,
a plain VM) — the Dockerfiles are platform-agnostic, only `render.yaml`
itself is Render-specific.

## Why Redis/Celery/Qdrant aren't deployed

`docker-compose.yml` (local dev) runs Postgres, Redis, Qdrant, the API, a
Celery worker, and the frontend. `render.yaml` only provisions Postgres +
the API + the frontend. That's deliberate, not an oversight: `GET
/api/v1/health/ready` only checks Postgres, and neither Redis (Celery's
broker) nor Qdrant (vector search) is wired into any use case a user can
actually reach today — the "pull as dataset" flow always runs inline
rather than through Celery (`run_async` exists on the request schema but
the UI never sets it), and nothing queries Qdrant yet. Deploying either
would just be an idle, unused service costing money. Add them to
`render.yaml` once a milestone actually depends on them.

## Deploy steps

1. **Get an Anthropic API key** from
   [console.anthropic.com](https://console.anthropic.com) if you don't
   have one — chat won't work without it (every agent turn will fail).
2. **Render dashboard → New → Blueprint**, select the `quantix-ai` GitHub
   repo. Render reads `render.yaml` and shows you the three resources it's
   about to create (`quantix-postgres`, `quantix-api`, `quantix-web`).
3. Render prompts for every `sync: false` value at this point — at minimum,
   set `ANTHROPIC_API_KEY` on `quantix-api`. Leave the OAuth client
   id/secret fields blank unless you've registered OAuth apps with
   Google/GitHub/Microsoft (email/password auth works regardless).
4. Click **Apply**. Render provisions Postgres first, then builds and
   deploys both web services from their Dockerfiles. First build takes
   several minutes (the API image installs from source; the web image runs
   a full Next.js production build).
5. Once both services show **Live**, visit:
   - `https://quantix-api.onrender.com/api/v1/docs` — should show the
     Swagger UI.
   - `https://quantix-web.onrender.com` — should show the landing page.
   - Register an account, log in, upload a dataset, start a chat
     conversation — see the root [README](../README.md)'s quickstart for
     the same walkthrough run locally.

If you renamed either service away from `quantix-api`/`quantix-web` during
step 2, update the cross-referencing env vars (`ALLOWED_ORIGINS`,
`FRONTEND_URL`, `API_PUBLIC_URL`, `NEXT_PUBLIC_API_BASE_URL`,
`NEXT_PUBLIC_APP_URL`, `NEXTAUTH_URL`) in each service's Environment tab to
match — `render.yaml` hardcodes the default names since Render doesn't
support variable interpolation between services in Blueprint files.

## Migrations

There's no separate migration step to remember: `apps/api/Dockerfile`'s
`CMD` runs `alembic upgrade head` before starting `uvicorn`, on every
container start. This was a deliberate choice over Render's
`preDeployCommand` field, which does the same job but is
[restricted to paid instance types](https://render.com/docs/blueprint-spec) —
baking it into the image instead means migrations run correctly on the
free plan too, and the same Dockerfile behaves identically on any other
host. `alembic upgrade head` is a no-op once the database is already
current, so this is safe on restarts, not just the first deploy.

## Known limitations of this deployment (free plan)

- **Free Postgres is deleted after 30 days**, with no warning and no
  automatic migration — confirmed current behavior as of writing. Fine for
  a demo/portfolio deployment; upgrade the database's plan in the Render
  dashboard before that if you want the data to persist longer.
- **Free web services spin down after 15 minutes of inactivity** and take
  30-60 seconds to cold-start on the next request — the first request
  after a period of no traffic will hang before responding. Upgrade to the
  Starter plan (~$7/mo/service) for always-on if that matters.
- **Uploaded dataset files don't survive a redeploy or restart.**
  `file_storage_dir`/`dataset_storage_dir` (see `core/config.py`) write to
  the container's local filesystem, which Render treats as ephemeral for
  Docker web services on the free plan. A dataset uploaded via
  `/datasets/upload` will disappear the next time the service restarts.
  Pluggable S3/GCS storage behind the same `FileStorage`/`DatasetStorage`
  ports is a documented follow-up (see ADR-0003), not yet built.
- **OAuth login buttons will error** unless you've filled in real
  Google/GitHub/Microsoft OAuth app credentials in each service's
  Environment tab (`sync: false` fields left blank at Blueprint creation).
  Email/password registration and login work regardless.

## Manual setup (if you'd rather not use the Blueprint)

Create each resource by hand in the Render dashboard instead of via
`render.yaml`:

1. **PostgreSQL** — New → PostgreSQL. Note the internal host/port/user/
   password/database it generates.
2. **API web service** — New → Web Service → same repo → Root Directory
   `apps/api` → Environment: Docker. Set the same env vars listed under
   `quantix-api` in `render.yaml` by hand, pointing `POSTGRES_*` at the
   database from step 1. Health Check Path: `/api/v1/health/live`.
3. **Web service** — New → Web Service → same repo → Root Directory
   `apps/web` → Environment: Docker. Set the env vars listed under
   `quantix-web`, pointing `NEXT_PUBLIC_API_BASE_URL` at the API service's
   URL from step 2 plus `/api/v1`.
