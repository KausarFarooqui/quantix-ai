"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { useLogout } from "@/features/auth/hooks";
import { useAuthStore } from "@/stores/auth-store";

const NAV_ITEMS = [
  { href: "/home", label: "Home" },
  { href: "/data-sources", label: "Data sources" },
  { href: "/datasets", label: "Datasets" },
  { href: "/chat", label: "Chat" },
];

/**
 * Shell for every authenticated route. Auth is enforced here, client-side,
 * rather than in Next.js middleware — the session lives in `localStorage`
 * via `useAuthStore` (see that file's docstring for why), and middleware
 * runs on the server/edge where `localStorage` doesn't exist. The guard
 * waits for `hasHydrated` before deciding to redirect, so an
 * already-logged-in user doesn't get bounced to `/login` for one render
 * on every page load while the persisted store is still reading back from
 * disk.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const hasHydrated = useAuthStore((state) => state.hasHydrated);
  const accessToken = useAuthStore((state) => state.accessToken);
  const user = useAuthStore((state) => state.user);
  const logout = useLogout();

  React.useEffect(() => {
    if (hasHydrated && !accessToken) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [hasHydrated, accessToken, pathname, router]);

  if (!hasHydrated || !accessToken) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading…</p>
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
