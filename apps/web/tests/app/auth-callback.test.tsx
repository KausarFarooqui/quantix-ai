import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";

import OAuthCallbackPage from "@/app/auth/callback/page";
import { useAuthStore } from "@/stores/auth-store";
import { renderWithQueryClient } from "../test-utils";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
}));

const getCurrentUser = vi.fn();
vi.mock("@/features/auth/api", () => ({
  authApi: {
    getCurrentUser: (...args: unknown[]) => getCurrentUser(...args),
  },
}));

const initialAuthState = useAuthStore.getState();

function setHash(hash: string) {
  window.location.hash = hash;
}

describe("OAuthCallbackPage", () => {
  beforeEach(() => {
    replace.mockClear();
    getCurrentUser.mockReset();
    useAuthStore.setState(initialAuthState, true);
    setHash("");
  });

  it("stores the session from the URL fragment and redirects home", async () => {
    getCurrentUser.mockResolvedValue({
      id: "u1",
      tenant_id: "t1",
      email: "a@example.com",
      full_name: "A User",
      role: "owner",
      is_active: true,
      is_email_verified: true,
    });
    setHash("#access_token=a1&refresh_token=r1&expires_in=900&is_new_account=false");

    renderWithQueryClient(<OAuthCallbackPage />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/home"));
    expect(useAuthStore.getState().accessToken).toBe("a1");
    expect(useAuthStore.getState().refreshToken).toBe("r1");
  });

  it("shows an error when the fragment is missing expected fields", async () => {
    setHash("");

    renderWithQueryClient(<OAuthCallbackPage />);

    expect(
      await screen.findByText("That sign-in link is missing or has expired. Please try again."),
    ).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("clears the session and shows an error if fetching the user fails", async () => {
    getCurrentUser.mockRejectedValue(new Error("boom"));
    setHash("#access_token=a1&refresh_token=r1&expires_in=900");

    renderWithQueryClient(<OAuthCallbackPage />);

    expect(
      await screen.findByText("Signed in, but couldn't load your account. Please try logging in again."),
    ).toBeInTheDocument();
    expect(useAuthStore.getState().accessToken).toBeNull();
  });
});
