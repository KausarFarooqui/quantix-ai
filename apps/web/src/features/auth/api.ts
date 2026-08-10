import { apiFetch, authFetch } from "@/lib/api-client";
import type { LoginRequest, LogoutRequest, RegisterRequest, TokenResponse, UserPublic } from "@/types/api";

/**
 * Typed calls against `/auth/*`. `demoLogin`/register/login use `apiFetch`
 * directly — there's no token yet to attach. Everything past that point
 * uses `authFetch` so an expired access token is transparently refreshed.
 *
 * There's no login/signup UI in this build (see `features/auth/hooks.ts`'s
 * `useDemoLogin` and ADR-0008) — `register`/`login` aren't called by
 * anything today, but stay here since the backend still fully supports
 * them and any future real sign-up UI should build on these rather than
 * reinventing them (see ADR-0008's follow-up note).
 */
export const authApi = {
  register: (body: RegisterRequest) =>
    apiFetch<TokenResponse>("/auth/register", { method: "POST", body }),

  login: (body: LoginRequest) => apiFetch<TokenResponse>("/auth/login", { method: "POST", body }),

  demoLogin: () => apiFetch<TokenResponse>("/auth/demo-login", { method: "POST" }),

  logout: (body: LogoutRequest) => authFetch<void>("/auth/logout", { method: "POST", body }),

  getCurrentUser: () => authFetch<UserPublic>("/auth/me"),
};
