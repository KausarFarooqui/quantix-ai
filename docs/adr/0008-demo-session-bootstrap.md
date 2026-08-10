# ADR-0008: Replace login/signup UI with a demo-session bootstrap

- **Status:** Accepted
- **Date:** 2026-08-11
- **Deciders:** Quantix AI engineering

## Context

Milestone 5 (ADR-0005) shipped `/login`, `/register`, an OAuth callback
route, and a client-side route guard that redirected unauthenticated
visitors to `/login`. In practice that flow was the main thing standing
between a visitor and the rest of the product: every new environment
needed a manual register-then-login round trip (or a working OAuth
provider) before any of milestones 6–7's actual functionality was
reachable, and iterating on the forms/OAuth callback themselves was
absorbing time that milestone 8+ work needed instead.

The backend's auth and multi-tenancy (ADR-0002) are not the problem —
they're solid, tested, and every route past `/auth/*` still depends on a
real `CurrentUser` resolved from a real JWT. The problem was specifically
the *visible* login/signup surface on the frontend.

An initial local fix bolted a `POST /auth/dev-login` endpoint onto the
backend — get-or-create a fixed dev tenant/user, mint real tokens, skip
the password check — and had the app shell call it instead of redirecting
to `/login`, but guarded it to 404 outside `Environment.DEVELOPMENT` and
documented it as a temporary shim to delete once "real auth" was working.
That guard was a latent production outage: once `/login` stopped being
linked from anywhere, a deployed environment would have had *no* working
entry point at all — the bypass 404s in production, and nothing points at
the still-present-but-orphaned login page. This ADR keeps that mechanism
but makes it permanent instead of removing it.

## Decision

**Remove the login/signup UI entirely; keep the backend's real auth
untouched.** `app/(auth)/login`, `app/(auth)/register`, and
`app/auth/callback` are deleted, along with the OAuth buttons and the
`zod` form schemas that only they used. `/auth/register`, `/auth/login`,
`/auth/refresh`, `/auth/logout`, `/auth/me`, and the OAuth routes are all
still there in `apps/api` and still enforce real tenant-scoped auth —
nothing about that layer changed.

**One new backend endpoint, `POST /auth/demo-login`, is the app's actual
entry point — permanently, in every environment.**
`application/use_cases/demo_login.py`'s `DemoLoginUseCase` get-or-creates
a single fixed tenant (`slug="demo"`) and owner user
(`demo@quantix.local`), skips password verification entirely (there's no
credential for an anonymous visitor to present), and mints a real token
pair through the same `issue_tokens` path every other login path uses.
It's idempotent — the first call anywhere against a given database
creates the account, every call after that (from any visitor, any tab)
just re-issues tokens for it.

Unlike the original dev-login shim, **this route has no environment
guard.** It has to work in production or the app has no way in at all.
The safety argument isn't "only reachable in dev" — it's that the account
it grants access to is intentionally public and shared, so an
unauthenticated way to obtain a valid session for it is the same thing as
the account existing at all.

**The app shell authenticates itself instead of redirecting.**
`app/(app)/layout.tsx` no longer redirects an unauthenticated visitor
anywhere — `useDemoLogin` (`features/auth/hooks.ts`) calls
`POST /auth/demo-login` in an effect, and the shell renders a loading
state until a session exists, or a connection-error state if that call
fails (rather than looping retries or silently hanging). The root route
(`app/page.tsx`) redirects straight to `/home` instead of rendering a
marketing page with "Log in" / "Get started" buttons pointing at pages
that no longer exist.

## Alternatives considered

- **Keep the dev-login endpoint dev-only, restore `/login` as the
  production path.** Rejected: reintroduces the exact UI problem this ADR
  exists to solve, just for one environment instead of all of them.
- **Have the frontend call the real `/auth/register` then `/auth/login`
  endpoints against a fixed demo identity**, instead of adding a
  dedicated backend endpoint. Considered and prototyped, but dropped in
  favor of the dev-login-turned-permanent approach once it existed: a
  direct get-or-create is simpler and race-safer than a
  try-login-then-register-then-retry-login dance, and doesn't need the
  frontend to reverse-engineer the backend's slug-generation rules to
  guess the right `tenant_slug` for login.
- **Strip auth and multi-tenancy out of the backend too**, collapsing to
  a single-tenant app with no tokens anywhere. Rejected: throws away
  tested, working infrastructure (JWT issuance, RBAC, audit logging,
  tenant scoping baked into the repository layer) that later milestones
  and any real multi-user deployment still want. The actual complaint was
  about the frontend surface, not the backend design.

## Consequences

**Positive:** every route is reachable immediately, in every environment
including production, with zero manual setup. Milestone 8+ work isn't
gated on auth UI. The backend's real auth design is untouched and still
fully exercised (real JWTs, real tenant scoping, real `/auth/me`), so it
stays truthfully tested rather than dead code.

**Negative:** there is currently no way for a real, distinct user to sign
up through the UI — everyone, in every deployment, shares one tenant and
one user record, and anyone who discovers `/auth/demo-login` can obtain a
valid session for it with no credential at all. That's an accepted
trade-off only because the account is meant to be shared and holds no
data any individual visitor should expect to be private. Real
multi-user/multi-tenant use needs the login/register UI (or an
equivalent) rebuilt on top of the still-intact backend before this app
could serve more than one distinct, private workspace.

**Follow-ups:** if/when real multi-tenant sign-up returns,
`authApi.register`/`authApi.login` (kept in `features/auth/api.ts`
specifically for this) are the place to build it on top of, reusing the
removed forms' validation constraints from
`interface/api/v1/schemas/auth.py` directly, same as ADR-0005 originally
did. At that point `/auth/demo-login` should either be deleted or kept
around only as an explicit "try it without an account" path, not the
sole entry point.
