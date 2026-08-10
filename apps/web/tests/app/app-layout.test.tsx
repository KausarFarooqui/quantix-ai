import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";

import AppLayout from "@/app/(app)/layout";
import { useAuthStore } from "@/stores/auth-store";
import { renderWithQueryClient } from "../test-utils";

vi.mock("next/navigation", () => ({
  usePathname: () => "/home",
}));

vi.mock("@/features/auth/api", () => ({
  authApi: {
    logout: vi.fn().mockResolvedValue(undefined),
    demoLogin: vi.fn(),
    getCurrentUser: vi.fn(),
  },
}));

import { authApi } from "@/features/auth/api";
import type { TokenResponse, UserPublic } from "@/types/api";

const demoUser: UserPublic = {
  id: "u1",
  tenant_id: "t1",
  email: "demo@quantix.local",
  full_name: "Demo User",
  role: "owner",
  is_active: true,
  is_email_verified: true,
};

const demoTokens: TokenResponse = {
  access_token: "tok",
  refresh_token: "refresh",
  token_type: "bearer",
  expires_in: 3600,
};

const initialAuthState = useAuthStore.getState();

describe("AppLayout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState(initialAuthState, true);
  });

  it("shows a loading state and does not attempt demo-login before the store has hydrated", () => {
    // Zustand's `persist` rehydration from localStorage typically finishes
    // before this test body even runs (it's not tied to React's render
    // cycle), so `hasHydrated` can't be relied on to still be `false` here
    // just because nothing has awaited yet — set it explicitly instead of
    // depending on that timing.
    useAuthStore.setState({ hasHydrated: false });

    renderWithQueryClient(
      <AppLayout>
        <p>Protected content</p>
      </AppLayout>,
    );

    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
    expect(authApi.demoLogin).not.toHaveBeenCalled();
  });

  it("silently bootstraps the demo session once hydrated with no access token", async () => {
    vi.mocked(authApi.demoLogin).mockResolvedValueOnce(demoTokens);
    vi.mocked(authApi.getCurrentUser).mockResolvedValueOnce(demoUser);
    useAuthStore.setState({ hasHydrated: true, accessToken: null });

    renderWithQueryClient(
      <AppLayout>
        <p>Protected content</p>
      </AppLayout>,
    );

    await waitFor(() => expect(screen.getByText("Protected content")).toBeInTheDocument());
    expect(authApi.demoLogin).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().user).toEqual(demoUser);
  });

  it("shows a connection error if demo-login fails, instead of a dead-end /login redirect", async () => {
    vi.mocked(authApi.demoLogin).mockRejectedValue(new Error("Failed to fetch"));
    useAuthStore.setState({ hasHydrated: true, accessToken: null });

    renderWithQueryClient(
      <AppLayout>
        <p>Protected content</p>
      </AppLayout>,
    );

    await waitFor(() =>
      expect(screen.getByText(/Couldn't connect to Quantix/)).toBeInTheDocument(),
    );
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
    // One failed attempt shouldn't loop retrying — `demoLogin.isError` gates
    // the effect off until something (e.g. a manual refresh) resets it.
    expect(authApi.demoLogin).toHaveBeenCalledTimes(1);
  });

  it("renders the shell and children once authenticated", () => {
    useAuthStore.setState({
      hasHydrated: true,
      accessToken: "token",
      user: demoUser,
    });

    renderWithQueryClient(
      <AppLayout>
        <p>Protected content</p>
      </AppLayout>,
    );

    expect(screen.getByText("Protected content")).toBeInTheDocument();
    expect(screen.getByText(/Demo User/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument();
  });
});
