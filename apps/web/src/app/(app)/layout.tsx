"use client";

import * as React from "react";
import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import { useDemoLogin, useLogout } from "@/features/auth/hooks";
import { useAuthStore } from "@/stores/auth-store";

// Typed as `Route` (not inferred as plain `string`) so each entry is
// checked against Next's `typedRoutes` route union at this declaration —
// `next build` runs a stricter type check than `tsc --noEmit` alone (it
// validates `Link href`s against generated route types), which a widened
// `string` fails even though plain `tsc --noEmit` doesn't catch it.
const NAV_ITEMS: { href: Route; label: string }[] = [
  { href: "/home", label: "Home" },
  { href: "/data-sources", label: "Data sources" },
  { href: "/datasets", label: "Datasets" },
  { href: "/chat", label: "Chat" },
];

/**
 * Shell for every route in the app. There's no login/signup UI (see
 * ADR-0008) — instead of redirecting an unauthenticated visitor to
 * `/login`, this shell silently authenticates them into a shared demo
 * workspace via `useDemoLogin` (`POST /auth/demo-login`) and only renders
 * the app once that session exists. The backend's real auth/multi-tenancy
 * is untouched; this just drives one specific, intentionally-public
 * account programmatically instead of through a form.
 *
 * The bootstrap waits for `hasHydrated` first so an already-hydrated
 * session from a previous visit isn't discarded and re-requested on every
 * page load while the persisted store is still reading back from disk.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const hasHydrated = useAuthStore((state) => state.hasHydrated);
  const accessToken = useAuthStore((state) => state.accessToken);
  const user = useAuthStore((state) => state.user);
  const logout = useLogout();
  const demoLogin = useDemoLogin();

  React.useEffect(() => {
    if (hasHydrated && !accessToken && !demoLogin.isPending && !demoLogin.isError) {
      demoLogin.mutate();
    }
    // demoLogin is intentionally omitted: it's a fresh mutation object each
    // render, so depending on it would re-fire this effect every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasHydrated, accessToken]);

  if (!hasHydrated || !accessToken) {
    return (
      <main className="flex min-h-screen items-center justify-center px-4 text-center">
        <p className="text-sm text-muted-foreground">
          {demoLogin.isError
            ? "Couldn't connect to Quantix. Check that the API is running, then refresh."
            : "Loading…"}
        </p>
      </main>
    );
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 flex-col gap-1 border-r border-border bg-card p-4">
        <Link href="/home" className="mb-4 px-2 text-lg font-bold tracking-tight">
          Quantix AI
        </Link>
        <nav className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => {
            // `startsWith` rather than an exact match so nested routes
            // (`/data-sources/new`, `/data-sources/[id]`) still highlight
            // their section in the nav.
            const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-md px-2 py-1.5 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground ${
                  isActive ? "bg-accent text-accent-foreground" : "text-muted-foreground"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex h-14 items-center justify-end gap-3 border-b border-border px-6">
          {user && (
            <span className="text-sm text-muted-foreground">
              {user.full_name} <span className="text-xs">({user.role})</span>
            </span>
          )}
          <Button variant="ghost" size="sm" onClick={() => logout.mutate()} disabled={logout.isPending}>
            {logout.isPending ? "Logging out…" : "Log out"}
          </Button>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
