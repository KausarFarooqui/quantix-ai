"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";
import { authApi } from "@/features/auth/api";
import type { OAuthProvider } from "@/types/api";

const PROVIDERS: { id: OAuthProvider; label: string }[] = [
  { id: "google", label: "Google" },
  { id: "github", label: "GitHub" },
  { id: "microsoft", label: "Microsoft" },
];

/**
 * Redirects the browser to the provider's consent screen. The backend
 * hands control back to `/auth/callback` with tokens in the URL fragment
 * (see `routes/oauth.py`) — that page finishes the flow.
 */
export function OAuthButtons({
  organizationName,
  disabled,
}: {
  /** Only meaningful on the register form — signals a new-tenant signup
   * rather than a login against an existing one.
   */
  organizationName?: string;
  disabled?: boolean;
}) {
  const [pendingProvider, setPendingProvider] = React.useState<OAuthProvider | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  async function handleClick(provider: OAuthProvider) {
    setError(null);
    setPendingProvider(provider);
    try {
      const { authorization_url } = await authApi.oauthAuthorizeUrl(provider, organizationName);
      window.location.href = authorization_url;
    } catch {
      setError("Couldn't start that sign-in — please try again.");
      setPendingProvider(null);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="grid grid-cols-3 gap-2">
        {PROVIDERS.map((provider) => (
          <Button
            key={provider.id}
            type="button"
            variant="outline"
            disabled={disabled || pendingProvider !== null}
            onClick={() => handleClick(provider.id)}
          >
            {pendingProvider === provider.id ? "…" : provider.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
