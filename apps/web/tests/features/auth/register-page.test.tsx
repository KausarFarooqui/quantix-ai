import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RegisterPage from "@/app/(auth)/register/page";
import { useAuthStore } from "@/stores/auth-store";
import { renderWithQueryClient } from "../../test-utils";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
}));

const registerCall = vi.fn();
const getCurrentUser = vi.fn();
vi.mock("@/features/auth/api", () => ({
  authApi: {
    register: (...args: unknown[]) => registerCall(...args),
    getCurrentUser: (...args: unknown[]) => getCurrentUser(...args),
    oauthAuthorizeUrl: vi.fn(),
  },
}));

const initialAuthState = useAuthStore.getState();

describe("RegisterPage", () => {
  beforeEach(() => {
    push.mockClear();
    registerCall.mockReset();
    getCurrentUser.mockReset();
    useAuthStore.setState(initialAuthState, true);
  });

  it("rejects a password shorter than 12 characters", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<RegisterPage />);

    await user.type(screen.getByLabelText("Password"), "short");
    await user.click(screen.getByRole("button", { name: "Create workspace" }));

    expect(await screen.findByText("Must be at least 12 characters")).toBeInTheDocument();
    expect(registerCall).not.toHaveBeenCalled();
  });

  it("rejects mismatched password confirmation", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<RegisterPage />);

    await user.type(screen.getByLabelText("Organization name"), "Acme Corp");
    await user.type(screen.getByLabelText("Your name"), "Ada Lovelace");
    await user.type(screen.getByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "correct-password-1");
    await user.type(screen.getByLabelText("Confirm password"), "different-password");
    await user.click(screen.getByRole("button", { name: "Create workspace" }));

    expect(await screen.findByText("Passwords don't match")).toBeInTheDocument();
    expect(registerCall).not.toHaveBeenCalled();
  });

  it("submits the form and redirects on success", async () => {
    registerCall.mockResolvedValue({
      access_token: "a",
      refresh_token: "r",
      token_type: "bearer",
      expires_in: 900,
    });
    getCurrentUser.mockResolvedValue({
      id: "u1",
      tenant_id: "t1",
      email: "ada@example.com",
      full_name: "Ada Lovelace",
      role: "owner",
      is_active: true,
      is_email_verified: true,
    });
    const user = userEvent.setup();
    renderWithQueryClient(<RegisterPage />);

    await user.type(screen.getByLabelText("Organization name"), "Acme Corp");
    await user.type(screen.getByLabelText("Your name"), "Ada Lovelace");
    await user.type(screen.getByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "correct-password-1");
    await user.type(screen.getByLabelText("Confirm password"), "correct-password-1");
    await user.click(screen.getByRole("button", { name: "Create workspace" }));

    await waitFor(() =>
      expect(registerCall).toHaveBeenCalledWith({
        organization_name: "Acme Corp",
        full_name: "Ada Lovelace",
        email: "ada@example.com",
        password: "correct-password-1",
      }),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/home"));
  });
});
