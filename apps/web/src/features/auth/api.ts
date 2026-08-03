import { apiFetch, authFetch } from "@/lib/api-client";
import type {
  LoginRequest,
  LogoutRequest,
  OAuthAuthorizeResponse,
  OAuthProvider,
  RegisterRequest,
  TokenResponse,
  UserPublic,
} from "@/types/api";

/**
 * Typed calls against `/auth/*`. Register/login use `apiFetch` directly —
 * there's no token yet to attach. Everything past that point uses
 * `authFetch` so an expired access token is transparently refreshed.
 */
export const authApi = {
  register: (body: RegisterRequest) =>
    apiFetch<TokenResponse>("/auth/register", { method: "POST", body }),

  login: (body: LoginRequest) => apiFetch<TokenResponse>("/auth/login", { method: "POST", body }),

  logout: (body: LogoutRequest) =>
    authFetch<void>("/auth/logout", { method: "POST", body }),

  getCurrentUser: () => authFetch<UserPublic>("/auth/me"),

  oauthAuthorizeUrl: (provider: OAuthProvider, organizationName?: string) => {
    const query = organizationName
      ? `?${new URLSearchParams({ organization_name: organizationName }).toString()}`
      : "";
    return apiFetch<OAuthAuthorizeResponse>(`/auth/oauth/${provider}/authorize${query}`);
  },
};
