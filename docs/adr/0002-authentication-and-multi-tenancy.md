# ADR-0002: Authentication, session model, and multi-tenant login

- **Status:** Accepted
- **Date:** 2026-08-03
- **Deciders:** Quantix AI engineering

## Context

Milestone 2 needed email/password auth, Google/GitHub/Microsoft OAuth,
RBAC, audit logging, and multi-tenant support, building on the
`tenant_id`-scoped schema established in ADR-0001. Two design questions
drove most of the shape of this milestone: how do revocable sessions work
alongside stateless JWTs, and how does login work when email is unique
*per tenant* rather than globally (the schema decision from milestone 1)?

## Decisions

**Hybrid token model.** Access tokens are short-lived, stateless JWTs
(15–60 min, signed HS256) — cheap to verify on every request, no DB hit.
Refresh tokens are opaque random strings, hashed with SHA-256 before
storage in a `refresh_tokens` table, so they're revocable (logout,
"log out everywhere", theft response) in a way a self-contained JWT
refresh token couldn't be. Every refresh rotates the token: the presented
token is revoked and a new one issued in the same operation. If an
already-revoked token is presented again — impossible in normal use,
since clients only ever present the token they were last given — that's
treated as reuse-after-theft and every refresh token for that user is
revoked immediately.

**Tenant-scoped login requires a tenant slug.** Because `users.email` is
unique per tenant (ADR-0001), `POST /auth/login` takes `tenant_slug` +
`email` + `password`, not just email. This mirrors how Slack, Linear, and
Notion handle multi-workspace login (a workspace identifier, then
credentials) rather than assuming global email uniqueness. **Follow-up,
not yet built:** a "find my workspaces" endpoint that looks up all
tenants a given email belongs to, for a friendlier login UX than making
users remember their slug.

**Registration always creates a new tenant.** There's no "join an
existing workspace via invite" flow yet — every `POST /auth/register`
provisions a brand-new tenant with the registering user as `OWNER`.
Invitations are explicitly out of scope for this milestone and tracked as
a follow-up.

**OAuth identity resolution is keyed on (provider, provider_user_id), not
email.** On callback, we look up the `oauth_accounts` table by the
provider's own subject ID first. If found, it's a returning user — no
tenant lookup needed, since the linked user record already has one. If
not found, it's treated as first-time signup: a new tenant is provisioned
(same as password registration) and the OAuth identity is linked to a new
owner user. Consequence: the same email address via two different
providers (or via OAuth vs. password) produces *separate, unlinked*
accounts today — there's no "sign in with Google to link to my existing
password account" flow. Also tracked as a follow-up; it requires the user
to already be authenticated when initiating the link, which the bare
OAuth callback isn't.

**OAuth state is a signed JWT, not server-side session storage.** CSRF
protection for the OAuth flow uses a short-TTL (10 min) signed token
carrying a nonce, the provider, the redirect URI, and an optional
organization-name hint — verified on callback, no Redis/session table
needed for this step.

**Tokens are handed to the frontend via a redirect URL fragment.** The
OAuth callback redirects to `{FRONTEND_URL}/auth/callback#access_token=...`.
Fragments aren't sent to servers or captured in access logs (unlike query
strings), which is why this is the fragment and not the query string —
but it's still a simplification versus the more robust pattern (httpOnly
`Set-Cookie` + one-time-code exchange) production hardening should move
to. Flagged explicitly rather than silently shipped as if it were the
final answer.

**Errors are deliberately uninformative on login, specific on
registration.** Every login failure path (unknown tenant, unknown email,
wrong password, OAuth-only account presenting a password) collapses to
one generic `InvalidCredentialsError` → HTTP 401, so the response can't be
used to enumerate valid accounts. Registration's duplicate-email check is
the opposite — specific and helpful (409, "this email is taken") — because
there's no credential to protect at that point; the information is no
more sensitive than what registering the same address again would already
reveal.

**RBAC via role ranking, enforced by dependency, not scattered checks.**
`UserRole` (owner > admin > analyst > viewer) with `User.has_at_least()`
in the domain layer; `require_role(min_role)` as a FastAPI dependency
factory applies it uniformly. No route should hand-roll a role check.

**Audit log is append-only and intentionally loose-schema.** A JSON
`metadata` column absorbs event-specific detail so new event types don't
need a migration. Every auth-relevant action (register, login
success/failure, logout, OAuth login, token refresh, token-reuse
detection) is recorded with actor, tenant, IP, and timestamp.

## Alternatives considered

- **Server-side sessions (cookie + session table) instead of
  JWT+refresh-token hybrid** — rejected: the API needs to serve a SPA
  frontend and, eventually, agent/service-to-service calls; stateless
  access-token verification avoids a DB round trip on every request while
  the refresh-token table still gives real revocation where it matters.
- **Global email uniqueness instead of per-tenant** — rejected (revisits
  ADR-0001): would simplify login but breaks the common B2B case of one
  person legitimately belonging to multiple customer workspaces with the
  same address.
- **`authlib` for OAuth instead of hand-rolled `httpx` clients** —
  rejected for now: three providers with plain authorization-code flow is
  a small, well-understood surface; a dependency earns its place once a
  fourth provider or a flow beyond authorization-code (PKCE, device flow)
  is needed.
- **JWT refresh tokens instead of opaque+hashed** — rejected: a
  self-contained refresh JWT can't be revoked before its own expiry
  without a denylist, which reintroduces the server-side state this
  design is trying to avoid for refresh tokens specifically — so the
  opaque+hashed approach isn't actually more complex, just correctly
  scoped.

## Consequences

**Positive:** revocation and reuse detection work without a distributed
session store; RBAC is enforced at a single choke point; audit trail
exists from day one instead of being retrofitted; the tenant-slug login
model doesn't require reworking the milestone-1 schema.

**Negative:** login UX requires knowing a workspace slug until the
"find my workspaces" follow-up ships; OAuth accounts can't self-link to
existing password accounts yet; the OAuth token handoff via URL fragment
is a known interim simplification, not the production-hardened final
form; no invitation system means every teammate currently has to register
their own tenant rather than join one.

**Follow-ups tracked for later milestones:** invitations/multi-user
tenants, "find my workspaces by email," OAuth account linking for
already-authenticated users, moving the OAuth token handoff to httpOnly
cookies + one-time code exchange, and closing the remaining test-coverage
gap on the OAuth authorize/callback routes (noted in the milestone
summary — these are the least-covered code paths in this milestone,
since they require mocking three external providers).
