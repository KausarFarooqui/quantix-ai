/**
 * Thin typed fetch wrapper around the Quantix API.
 *
 * Feature modules build on this rather than calling `fetch` directly, so
 * auth headers, error normalization, and the base URL live in one place.
 */

import { useAuthStore } from "@/stores/auth-store";
import type { TokenResponse } from "@/types/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly errorType?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  accessToken?: string;
}

export async function apiFetch<TResponse>(
  path: string,
  { body, accessToken, headers, ...init }: RequestOptions = {},
): Promise<TResponse> {
  // `FormData` (file uploads) must go through as-is: the browser sets its
  // own `multipart/form-data; boundary=...` Content-Type when none is
  // supplied, which is why that header is omitted rather than forced to
  // `application/json` in this branch. JSON-stringifying a `FormData`
  // instance would silently serialize it to `"{}"` instead of sending the
  // file.
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...headers,
    },
    body: isFormData ? (body as FormData) : body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new ApiError(
      payload.detail ?? `Request to ${path} failed with ${response.status}`,
      response.status,
      payload.error_type,
    );
  }

  if (response.status === 204) {
    return undefined as TResponse;
  }

  return (await response.json()) as TResponse;
}

let refreshInFlight: Promise<string> | null = null;

/**
 * Exchanges the stored refresh token for a new pair via `POST
 * /auth/refresh`, updating the auth store. Concurrent 401s (e.g. several
 * queries in flight when the access token expires) share a single
 * in-flight refresh rather than each firing their own — refresh tokens
 * rotate on use (see ADR-0002), so a second concurrent call would revoke
 * the token the first call is still waiting on.
 */
async function refreshSession(): Promise<string> {
  if (refreshInFlight) {
    return refreshInFlight;
  }

  const { refreshToken } = useAuthStore.getState();
  if (!refreshToken) {
    useAuthStore.getState().clearSession();
    throw new ApiError("Not authenticated", 401);
  }

  refreshInFlight = (async () => {
    try {
      const response = await apiFetch<TokenResponse>("/auth/refresh", {
        method: "POST",
        body: { refresh_token: refreshToken },
      });
      useAuthStore.getState().setSession({
        accessToken: response.access_token,
        refreshToken: response.refresh_token,
        expiresIn: response.expires_in,
      });
      return response.access_token;
    } catch (error) {
      useAuthStore.getState().clearSession();
      throw error;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

/**
 * Like `apiFetch`, but attaches the current access token automatically and
 * transparently retries once via `refreshSession()` on a 401 — the
 * pattern every authenticated feature-module call should use instead of
 * `apiFetch` directly.
 */
export async function authFetch<TResponse>(
  path: string,
  options: RequestOptions = {},
): Promise<TResponse> {
  const { accessToken } = useAuthStore.getState();

  try {
    return await apiFetch<TResponse>(path, { ...options, accessToken: accessToken ?? undefined });
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) {
      throw error;
    }
    if (!useAuthStore.getState().refreshToken) {
      // No refresh token to fall back on — this access token isn't coming
      // back. Clear the stale session so the route guard reacts (redirects
      // to `/login`) instead of leaving an invalid token sitting in the
      // store indefinitely.
      useAuthStore.getState().clearSession();
      throw error;
    }
    const newAccessToken = await refreshSession();
    return apiFetch<TResponse>(path, { ...options, accessToken: newAccessToken });
  }
}
