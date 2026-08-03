"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { authApi } from "@/features/auth/api";
import { useAuthStore } from "@/stores/auth-store";
import type { LoginRequest, RegisterRequest, TokenResponse } from "@/types/api";

const currentUserQueryKey = ["auth", "me"] as const;

/** Shared by useLogin/useRegister — save the token pair, then fetch and
 * cache the user record rather than trusting the client to reconstruct it
 * (the register/login responses only carry tokens; `/auth/me` is the
 * single source of truth for the user shape).
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

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: RegisterRequest) => authApi.register(body),
    onSuccess: (tokens) => establishSession(tokens, queryClient),
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: LoginRequest) => authApi.login(body),
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
      // session takes priority over a clean server-side revoke.
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
