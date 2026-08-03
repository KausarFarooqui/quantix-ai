"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api-client";
import { useRegister } from "@/features/auth/hooks";
import { OAuthButtons } from "@/features/auth/oauth-buttons";
import { type RegisterFormValues, registerSchema } from "@/features/auth/schemas";

export default function RegisterPage() {
  const router = useRouter();
  const registerAccount = useRegister();
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RegisterFormValues>({ resolver: zodResolver(registerSchema) });

  async function onSubmit(values: RegisterFormValues) {
    registerAccount.mutate(
      {
        organization_name: values.organizationName,
        full_name: values.fullName,
        email: values.email,
        password: values.password,
      },
      { onSuccess: () => router.push("/home") },
    );
  }

  const errorMessage =
    registerAccount.error instanceof ApiError
      ? registerAccount.error.message
      : registerAccount.error
        ? "Something went wrong — please try again."
        : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create your workspace</CardTitle>
        <CardDescription>You&apos;ll be the owner of this new Quantix workspace.</CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <CardContent className="flex flex-col gap-4">
          {errorMessage && (
            <Alert variant="destructive">
              <AlertDescription>{errorMessage}</AlertDescription>
            </Alert>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="organizationName">Organization name</Label>
            <Input id="organizationName" autoComplete="organization" {...register("organizationName")} />
            {errors.organizationName && (
              <p className="text-sm text-destructive">{errors.organizationName.message}</p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fullName">Your name</Label>
            <Input id="fullName" autoComplete="name" {...register("fullName")} />
            {errors.fullName && <p className="text-sm text-destructive">{errors.fullName.message}</p>}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" {...register("email")} />
            {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" autoComplete="new-password" {...register("password")} />
            {errors.password && <p className="text-sm text-destructive">{errors.password.message}</p>}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="confirmPassword">Confirm password</Label>
            <Input
              id="confirmPassword"
              type="password"
              autoComplete="new-password"
              {...register("confirmPassword")}
            />
            {errors.confirmPassword && (
              <p className="text-sm text-destructive">{errors.confirmPassword.message}</p>
            )}
          </div>

          <Button type="submit" disabled={registerAccount.isPending} className="mt-2">
            {registerAccount.isPending ? "Creating workspace…" : "Create workspace"}
          </Button>

          <div className="relative py-2 text-center text-xs text-muted-foreground">
            <span className="relative z-10 bg-card px-2">or continue with</span>
            <div className="absolute inset-x-0 top-1/2 -z-0 h-px bg-border" />
          </div>

          <OAuthButtons organizationName={watch("organizationName")} disabled={registerAccount.isPending} />
        </CardContent>
      </form>
      <CardFooter className="justify-center text-sm text-muted-foreground">
        Already have a workspace?&nbsp;
        <Link href="/login" className="font-medium text-primary hover:underline">
          Log in
        </Link>
      </CardFooter>
    </Card>
  );
}
