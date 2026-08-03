# ADR-0005: Frontend authentication, session storage, and route protection

- **Status:** Accepted
- **Date:** 2026-08-03
- **Deciders:** Quantix AI engineering

## Context

Milestone 5 gives the Next.js frontend its first real pages: `/login`,
`/register`, the OAuth redirect target, and a protected app shell. The
backend (ADR-0002) issues stateless JWT access tokens plus a revocable
opaque refresh token, with no server-side session and no cookie support —
so the frontend has to decide where a browser tab keeps that pair between
page loads, how a route decides whether the visitor is signed in, and how
an expired access token gets renewed without the user noticing.

## Decisions

**Session state lives in a persisted Zustand store, not TanStack Query.**
`stores/auth-store.ts` holds the access/refresh token pair and the current
user, persisted to `localStorage`. This is a deliberate, documented
exception to the project's usual rule ("TanStack Query owns server data,
Zustand owns UI-only state" — see `ARCHITECTURE.md` §4): the API client
and the route guard are plain functions and a layout component that need
to read the token *synchronously*, outside of any component that's
subscribed to a query. `useAuthStore.getState()` works from anywhere;
a `useQuery` result doesn't.

**Tokens are stored in `localStorage`, not an httpOnly cookie.** The
backend has no session to hang a cookie off — access tokens are verified
by signature alone (ADR-0002) — so there's no server-side mechanism to set
one today. This carries the same trade-off ADR-0002 already flagged for
the OAuth fragment handoff: tokens are JS-reachable, which is weaker
against XSS than an httpOnly cookie would be. Tracked as the same
follow-up ADR-0002 already tracks (move to httpOnly cookie + one-time-code
exchange), not a new problem introduced here.

**Route protection is a client-side guard, not Next.js middleware.**
`app/(app)/layout.tsx` checks the auth store and redirects to `/login` in
an effect. Middleware runs on the server/edge, where `localStorage`
doesn't exist, so it can't see this session at all without also adopting
cookies — which isn't happening yet per the decision above. The guard
waits for a `hasHydrated` flag (set once Zustand's `persist` middleware
has read `localStorage` back) before deciding to redirect, so a
already-logged-in user doesn't get bounced to `/login` for one render on
every page load while the store is still rehydrating.

**`authFetch` retries once on 401 via a shared, de-duplicated refresh.**
`lib/api-client.ts` exports `authFetch`, layered on the existing
`apiFetch`: it attaches the current access token, and on a 401 calls
`POST /auth/refresh` once, updates the store, and retries the original
request. Concurrent 401s share a single in-flight refresh promise rather
than each firing their own — refresh tokens rotate on use (ADR-0002), so a
second concurrent refresh call would revoke the token the first one is
still waiting on, breaking both.

**The OAuth callback reads the URL fragment directly, in its own route
segment.** The backend redirects to `{FRONTEND_URL}/auth/callback#access_
token=...` (ADR-0002) — fragments never reach the server or
`useSearchParams()` (which only sees the query string), so
`app/auth/callback/page.tsx` is a real path segment (not the `(auth)`
route group used for `/login`/`/register`, which shares no URL with it) whose
client component parses `window.location.hash` in an effect.

**Forms validate with `zod` schemas mirrored from the backend's Pydantic
constraints, using `react-hook-form` + `@hookform/resolvers`.** Client-side
validation is a UX convenience only — the backend re-validates and remains
the source of truth — but mirroring the constraints (password length,
slug format, field lengths) means most invalid submissions never round-trip
to the API at all.

## Alternatives considered

- **NextAuth.js** — rejected for this milestone: NextAuth is built around
  provider-driven sessions (its own JWT or database session), which
  overlaps awkwardly with a backend that already issues its own access +
  refresh token pair and expects to verify them itself. Revisit if a
  future milestone wants NextAuth's broader provider ecosystem or CSRF
  handling instead of the hand-rolled OAuth-button flow here.
- **httpOnly cookies via a Next.js Route Handler proxying the API** —
  rejected for now: would fix the XSS exposure noted above, but requires
  the Next.js server to sit in the request path for every authenticated
  call (defeating direct browser→API calls) and a CSRF strategy on top.
  Real hardening path, deliberately deferred alongside the same tracked
  item in ADR-0002 rather than solved partially here.
- **Storing only the access token client-side, keeping the refresh token
  in memory only (lost on tab close)** — rejected: would force a full
  re-login on every tab close/refresh, which is a worse UX than the
  XSS-exposure trade-off this ADR already accepts for the access token.

## Consequences

**Positive:** the API client, not every feature module, owns
token-attachment and refresh-retry logic — call sites just use `authFetch`
and never think about 401s. The guard's hydration wait avoids a login-page
flash for returning users. The callback page and route guard are both
small, easily-testable units with no framework magic to fight.

**Negative:** tokens are JS-reachable (XSS exposure), same open item
ADR-0002 already tracks for the OAuth fragment handoff — this ADR doesn't
close it, just doesn't make it worse. No Next.js middleware means no
edge-level redirect; an unauthenticated visitor to a protected route gets
a real (client-rendered) page load before the redirect fires, which is a
minor performance/flash cost versus a cookie-based middleware redirect.

**Follow-ups tracked for later milestones:** move to httpOnly cookie +
one-time-code exchange (shared with ADR-0002's tracked item); a "remember
me" vs. session-only token lifetime choice on login; surfacing a
visible session-expiry warning before the access token lapses rather than
relying entirely on the silent refresh-and-retry.
