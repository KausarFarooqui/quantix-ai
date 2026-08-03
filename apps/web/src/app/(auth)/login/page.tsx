"use client";

import * as React from "react";
import Link from "next/link";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api-client";
import { useLogin } from "@/features/auth/hooks";
import { OAuthButtons } from "@/features/auth/oauth-buttons";
import { type LoginFormValues, loginSchema } from "@/features/auth/schemas";

export default function LoginPage() {
  const router = useRouter();
  const login = useLogin();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });

  // Read `?next=` via `window.location` rather than `useSearchParams()` —
  // the latter forces this statically-renderable page into a Suspense
  // boundary in the App Router; reading it in an effect avoids that for
  // one query param this page only needs after a submit, never on first
  // paint. (`app/(app)/layout.tsx`'s auth guard is what sets `next`.)
  const [redirectTo, setRedirectTo] = React.useState<Route>("/home");
  React.useEffect(() => {
    const next = new URLSearchParams(window.location.search).get("next");
    // Only accept a same-origin path (a single leading "/", not "//host/…"
    // which browsers treat as protocol-relative to another origin) — this
    // value is attacker-controllable via the query string and ends up in
    // `router.push()`. The `as Route` cast is otherwise safe here because
    // of that same-origin check, not despite it.
    if (next && next.startsWith("/") && !next.startsWith("//")) {
      setRedirectTo(next as Route);
    }
  }, []);

  async function onSubmit(values: LoginFormValues) {
    login.mutate(
      {
        tenant_slug: values.tenantSlug,
        email: values.email,
        password: values.password,
      },
      { onSuccess: () => router.push(redirectTo) },
    );
  }

  const errorMessage =
    login.error instanceof ApiError
      ? login.error.message
      : login.error
        ? "Something went wrong — please try again."
        : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Log in</CardTitle>
        <CardDescription>Welcome back — enter your workspace to continue.</CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <CardContent className="flex flex-col gap-4">
          {errorMessage && (
            <Alert variant="destructive">
              <AlertDescription>{errorMessage}</AlertDescription>
            </Alert>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="tenantSlug">Workspace</Label>
            <Input
              id="tenantSlug"
              placeholder="acme"
              autoComplete="organization"
              {...register("tenantSlug")}
            />
            {errors.tenantSlug && <p className="text-sm text-destructive">{errors.tenantSlug.message}</p>}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" {...register("email")} />
            {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" autoComplete="current-password" {...register("password")} />
            {errors.password && <p className="text-sm text-destructive">{errors.password.message}</p>}
          </div>

          <Button type="submit" disabled={login.isPending} className="mt-2">
            {login.isPending ? "Logging in…" : "Log in"}
          </Button>

          <div className="relative py-2 text-center text-xs text-muted-foreground">
            <span className="relative z-10 bg-card px-2">or continue with</span>
            <div className="absolute inset-x-0 top-1/2 -z-0 h-px bg-border" />
          </div>

          <OAuthButtons disabled={login.isPending} />
        </CardContent>
      </form>
      <CardFooter className="justify-center text-sm text-muted-foreground">
        Don&apos;t have a workspace?&nbsp;
        <Link href="/register" className="font-medium text-primary hover:underline">
          Create one
        </Link>
      </CardFooter>
    </Card>
  );
}
