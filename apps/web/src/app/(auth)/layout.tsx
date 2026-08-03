import Link from "next/link";

/**
 * Shared centered-card chrome for `/login` and `/register`. A route group
 * (`(auth)`, parens) — doesn't add a URL segment, unlike `app/auth/callback`
 * (see that route's comment for why it's a real segment instead).
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 bg-muted/30 px-4 py-12">
      <Link href="/" className="text-xl font-bold tracking-tight">
        Quantix AI
      </Link>
      <div className="w-full max-w-md">{children}</div>
    </main>
  );
}
