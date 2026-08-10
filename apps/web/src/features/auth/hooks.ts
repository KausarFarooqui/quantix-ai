"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { authApi } from "@/features/auth/api";
import { useAuthStore } from "@/stores/auth-store";
import type { TokenResponse } from "@/types/api";

const currentUserQueryKey = ["auth", "me"] as const;

/**
 * There's no login/signup UI in this build (see ADR-0008) — save the
 * token pair, then fetch and cache the user record rather than trusting
 * the client to reconstruct it (`/auth/demo-login`'s response only
 * carries tokens; `/auth/me` is the single source of truth for the user
 * shape). Shared by `useDemoLogin` and `useLogout`'s cache-clear path.
 */
async function establishSession(tokens: TokenResponse, queryClient: ReturnType<typeof useQueryClient>) {
  useAuthStore.getState().setSession({
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    expiresIn: tokens.expires_in,
  });
  const user = await authApi.getCurrentUser();
  useAuthStore.getState().setUser(user);
  queryClient.setQueryData(currentUserQueryKey, user);
}

/**
 * Bootstraps a session for the shared demo workspace via
 * `POST /auth/demo-login` — no credentials involved. This is the app's
 * permanent auth entry point (see ADR-0008), called from
 * `app/(app)/layout.tsx`'s app-shell guard in place of a `/login`
 * redirect.
 */
export function useDemoLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => authApi.demoLogin(),
    onSuccess: (tokens) => establishSession(tokens, queryClient),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { refreshToken } = useAuthStore.getState();
      if (refreshToken) {
        await authApi.logout({ refresh_token: refreshToken });
      }
    },
    onSettled: () => {
      // Log out client-side even if the network call failed (token
      // already expired, offline, etc.) — the user's intent to leave the
      // session takes priority over a clean server-side revoke. The app
      // shell's guard will silently call `useDemoLogin` again on the next
      // render, since there's no login page to land on instead.
      useAuthStore.getState().clearSession();
      queryClient.clear();
    },
  });
}

export function useCurrentUser() {
  const accessToken = useAuthStore((state) => state.accessToken);
  return useQuery({
    queryKey: currentUserQueryKey,
    queryFn: authApi.getCurrentUser,
    enabled: accessToken !== null,
    staleTime: 5 * 60_000,
  });
}
