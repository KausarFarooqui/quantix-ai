import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { UserPublic } from "@/types/api";

interface SessionInput {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  user?: UserPublic | null;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  /** Epoch milliseconds the access token expires at — advisory only; the
   * source of truth for "is this token still good" is the API's 401
   * response, handled by `lib/api-client.ts`'s refresh-and-retry logic.
   */
  expiresAt: number | null;
  user: UserPublic | null;
  /** True once the persisted state has been read back from localStorage.
   * Route guards must wait for this before deciding to redirect to
   * `/login` — otherwise an already-logged-in user gets bounced for one
   * render on every page load/refresh, before hydration catches up.
   */
  hasHydrated: boolean;
  setSession: (session: SessionInput) => void;
  setUser: (user: UserPublic) => void;
  clearSession: () => void;
  setHasHydrated: (value: boolean) => void;
}

/**
 * Holds the auth/session state: access + refresh tokens and the current
 * user. This is a deliberate exception to "Zustand is UI-only state" (see
 * `ui-store.ts`) — session state needs to be readable synchronously from
 * plain functions (`lib/api-client.ts`'s `authFetch`, route guards) that
 * aren't React components and can't subscribe to a TanStack Query cache.
 * `useAuthStore.getState()` / `.setState()` work outside components for
 * exactly this reason.
 *
 * Persisted to localStorage rather than an httpOnly cookie because the
 * backend issues stateless JWTs with no server-side session to hang a
 * cookie off (see ADR-0002) — tracked as a documented hardening follow-up
 * in ADR-0005, not a milestone-5 blocker.
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      expiresAt: null,
      user: null,
      hasHydrated: false,
      setSession: ({ accessToken, refreshToken, expiresIn, user }) =>
        set((state) => ({
          accessToken,
          refreshToken,
          expiresAt: Date.now() + expiresIn * 1000,
          user: user !== undefined ? user : state.user,
        })),
      setUser: (user) => set({ user }),
      clearSession: () =>
        set({ accessToken: null, refreshToken: null, expiresAt: null, user: null }),
      setHasHydrated: (value) => set({ hasHydrated: value }),
    }),
    {
      name: "quantix-auth",
      // `hasHydrated` is deliberately excluded — it describes the state of
      // the persistence mechanism itself, not something to persist.
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        expiresAt: state.expiresAt,
        user: state.user,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    },
  ),
);

export function isAuthenticated(): boolean {
  return useAuthStore.getState().accessToken !== null;
}
