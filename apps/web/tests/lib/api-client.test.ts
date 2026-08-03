import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch, ApiError, authFetch } from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";

const initialAuthState = useAuthStore.getState();

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe("apiFetch", () => {
  beforeEach(() => {
    useAuthStore.setState(initialAuthState, true);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed JSON on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, { status: "ok" })),
    );

    const result = await apiFetch<{ status: string }>("/health/live");

    expect(result).toEqual({ status: "ok" });
  });

  it("throws ApiError with the backend's detail message on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(404, { detail: "Not found", error_type: "EntityNotFoundError" })),
    );

    await expect(apiFetch("/datasets/does-not-exist")).rejects.toMatchObject({
      message: "Not found",
      status: 404,
      errorType: "EntityNotFoundError",
    });
  });

  it("returns undefined for a 204 response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 204 } as Response));

    const result = await apiFetch("/auth/logout", { method: "POST" });

    expect(result).toBeUndefined();
  });
});

describe("authFetch", () => {
  beforeEach(() => {
    useAuthStore.setState(initialAuthState, true);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("attaches the current access token", async () => {
    useAuthStore.getState().setSession({ accessToken: "token-1", refreshToken: "r1", expiresIn: 900 });
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, {}));
    vi.stubGlobal("fetch", fetchMock);

    await authFetch("/auth/me");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer token-1");
  });

  it("refreshes once on a 401 and retries the original request", async () => {
    useAuthStore.getState().setSession({ accessToken: "stale", refreshToken: "refresh-1", expiresIn: 900 });

    const fetchMock = vi
      .fn()
      // Original request — rejected as expired.
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Token expired" }))
      // POST /auth/refresh — succeeds with a new pair.
      .mockResolvedValueOnce(
        jsonResponse(200, {
          access_token: "fresh",
          refresh_token: "refresh-2",
          token_type: "bearer",
          expires_in: 900,
        }),
      )
      // Retried original request — succeeds.
      .mockResolvedValueOnce(jsonResponse(200, { id: "user-1" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await authFetch<{ id: string }>("/auth/me");

    expect(result).toEqual({ id: "user-1" });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(useAuthStore.getState().accessToken).toBe("fresh");
    expect(useAuthStore.getState().refreshToken).toBe("refresh-2");
    const [, retryInit] = fetchMock.mock.calls[2] as [string, RequestInit];
    expect((retryInit.headers as Record<string, string>).Authorization).toBe("Bearer fresh");
  });

  it("clears the session and rejects when there is no refresh token to fall back on", async () => {
    useAuthStore.getState().setSession({ accessToken: "stale", refreshToken: "r", expiresIn: 900 });
    useAuthStore.setState({ refreshToken: null });

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(401, { detail: "Token expired" })));

    await expect(authFetch("/auth/me")).rejects.toBeInstanceOf(ApiError);
    expect(useAuthStore.getState().accessToken).toBeNull();
  });

  it("clears the session when the refresh call itself fails", async () => {
    useAuthStore.getState().setSession({ accessToken: "stale", refreshToken: "refresh-1", expiresIn: 900 });

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Token expired" }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Refresh token revoked" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(authFetch("/auth/me")).rejects.toBeInstanceOf(ApiError);
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(useAuthStore.getState().refreshToken).toBeNull();
  });
});
