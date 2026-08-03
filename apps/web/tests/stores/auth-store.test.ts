import { beforeEach, describe, expect, it } from "vitest";

import { isAuthenticated, useAuthStore } from "@/stores/auth-store";

const initialState = useAuthStore.getState();

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.setState(initialState, true);
    localStorage.clear();
  });

  it("starts with no session", () => {
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it("setSession stores the token pair and computes an expiry", () => {
    const before = Date.now();
    useAuthStore.getState().setSession({
      accessToken: "access-1",
      refreshToken: "refresh-1",
      expiresIn: 900,
    });

    const state = useAuthStore.getState();
    expect(state.accessToken).toBe("access-1");
    expect(state.refreshToken).toBe("refresh-1");
    expect(state.expiresAt).toBeGreaterThanOrEqual(before + 900_000);
    expect(isAuthenticated()).toBe(true);
  });

  it("setSession without a user preserves the previously-stored user", () => {
    const user = {
      id: "u1",
      tenant_id: "t1",
      email: "a@example.com",
      full_name: "A User",
      role: "owner" as const,
      is_active: true,
      is_email_verified: true,
    };
    useAuthStore.getState().setUser(user);

    useAuthStore.getState().setSession({ accessToken: "a2", refreshToken: "r2", expiresIn: 60 });

    expect(useAuthStore.getState().user).toEqual(user);
  });

  it("clearSession resets tokens and user", () => {
    useAuthStore.getState().setSession({ accessToken: "a", refreshToken: "r", expiresIn: 60 });

    useAuthStore.getState().clearSession();

    const state = useAuthStore.getState();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.user).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it("persists the session to localStorage", () => {
    useAuthStore.getState().setSession({ accessToken: "a", refreshToken: "r", expiresIn: 60 });

    const raw = localStorage.getItem("quantix-auth");
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw!).state.accessToken).toBe("a");
  });
});
