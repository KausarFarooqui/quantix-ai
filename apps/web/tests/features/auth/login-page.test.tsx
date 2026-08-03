import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import LoginPage from "@/app/(auth)/login/page";
import { ApiError } from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import { renderWithQueryClient } from "../../test-utils";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
}));

const login = vi.fn();
const getCurrentUser = vi.fn();
vi.mock("@/features/auth/api", () => ({
  authApi: {
    login: (...args: unknown[]) => login(...args),
    getCurrentUser: (...args: unknown[]) => getCurrentUser(...args),
    oauthAuthorizeUrl: vi.fn(),
  },
}));

const initialAuthState = useAuthStore.getState();

describe("LoginPage", () => {
  beforeEach(() => {
    push.mockClear();
    login.mockReset();
    getCurrentUser.mockReset();
    useAuthStore.setState(initialAuthState, true);
  });

  it("renders the workspace, email, and password fields", () => {
    renderWithQueryClient(<LoginPage />);

    expect(screen.getByLabelText("Workspace")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("shows validation errors instead of submitting an empty form", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<LoginPage />);

    await user.click(screen.getByRole("button", { name: "Log in" }));

    // Both the workspace and password fields are empty, and both fail
    // their `min(1, "Required")` check — two matches, not one.
    expect(await screen.findAllByText("Required")).toHaveLength(2);
    expect(screen.getByText("Enter a valid email address")).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it("submits the form and redirects on success", async () => {
    login.mockResolvedValue({
      access_token: "a",
      refresh_token: "r",
      token_type: "bearer",
      expires_in: 900,
    });
    getCurrentUser.mockResolvedValue({
      id: "u1",
      tenant_id: "t1",
      email: "a@example.com",
      full_name: "A User",
      role: "owner",
      is_active: true,
      is_email_verified: true,
    });
    const user = userEvent.setup();
    renderWithQueryClient(<LoginPage />);

    await user.type(screen.getByLabelText("Workspace"), "acme");
    await user.type(screen.getByLabelText("Email"), "a@example.com");
    await user.type(screen.getByLabelText("Password"), "correct-password");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() =>
      expect(login).toHaveBeenCalledWith({
        tenant_slug: "acme",
        email: "a@example.com",
        password: "correct-password",
      }),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/home"));
    expect(useAuthStore.getState().accessToken).toBe("a");
  });

  it("shows the API's error message when login fails", async () => {
    login.mockRejectedValue(new ApiError("Invalid credentials", 401));
    const user = userEvent.setup();
    renderWithQueryClient(<LoginPage />);

    await user.type(screen.getByLabelText("Workspace"), "acme");
    await user.type(screen.getByLabelText("Email"), "a@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByText("Invalid credentials")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});
