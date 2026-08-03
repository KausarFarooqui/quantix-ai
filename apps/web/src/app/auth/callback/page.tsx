"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { authApi } from "@/features/auth/api";
import { useAuthStore } from "@/stores/auth-store";

/**
 * `GET /auth/oauth/{provider}/callback` on the backend finishes the OAuth
 * exchange server-side and redirects the browser here with tokens in the
 * URL *fragment* (`#access_token=...`), not the query string — fragments
 * never reach the server, so this has to be a real path segment (not the
 * `(auth)` route group, which shares no URL with this) with a client
 * component that reads `window.location.hash` directly; `useSearchParams`
 * only sees the query string and would never see these values.
 */
export default function OAuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");
    const expiresIn = Number(params.get("expires_in"));

    if (!accessToken || !refreshToken || Number.isNaN(expiresIn)) {
      setError("That sign-in link is missing or has expired. Please try again.");
      return;
    }

    useAuthStore.getState().setSession({ accessToken, refreshToken, expiresIn });

    authApi
      .getCurrentUser()
      .then((user) => {
        useAuthStore.getState().setUser(user);
        router.replace("/home");
      })
      .catch(() => {
        useAuthStore.getState().clearSession();
        setError("Signed in, but couldn't load your account. Please try logging in again.");
      });
  }, [router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 px-4 text-center">
      {error ? (
        <>
          <p className="text-sm text-destructive">{error}</p>
          <a href="/login" className="text-sm font-medium text-primary hover:underline">
            Back to login
          </a>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">Finishing sign-in…</p>
      )}
    </main>
  );
}
