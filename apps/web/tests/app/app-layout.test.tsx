import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";

import AppLayout from "@/app/(app)/layout";
import { useAuthStore } from "@/stores/auth-store";
import { renderWithQueryClient } from "../test-utils";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  usePathname: () => "/home",
}));

vi.mock("@/features/auth/api", () => ({
  authApi: {
    logout: vi.fn().mockResolvedValue(undefined),
  },
}));

const initialAuthState = useAuthStore.getState();

describe("AppLayout", () => {
  beforeEach(() => {
    replace.mockClear();
    useAuthStore.setState(initialAuthState, true);
  });

  it("shows a loading state and does not redirect before the store has hydrated", () => {
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
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects to /login once hydrated with no access token", async () => {
    useAuthStore.setState({ hasHydrated: true, accessToken: null });

    renderWithQueryClient(
      <AppLayout>
        <p>Protected content</p>
      </AppLayout>,
    );

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?next=%2Fhome"));
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("renders the shell and children once authenticated", () => {
    useAuthStore.setState({
      hasHydrated: true,
      accessToken: "token",
      user: {
        id: "u1",
        tenant_id: "t1",
        email: "a@example.com",
        full_name: "Ada Lovelace",
        role: "owner",
        is_active: true,
        is_email_verified: true,
      },
    });

    renderWithQueryClient(
      <AppLayout>
        <p>Protected content</p>
      </AppLayout>,
    );

    expect(screen.getByText("Protected content")).toBeInTheDocument();
    expect(screen.getByText(/Ada Lovelace/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
