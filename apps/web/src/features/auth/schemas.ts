import { z } from "zod";

/**
 * Client-side validation mirrors the backend's Pydantic constraints
 * (`interface/api/v1/schemas/auth.py`) so obviously-invalid submissions
 * never round-trip to the API — the backend remains the source of truth
 * and re-validates everything regardless.
 */

export const registerSchema = z
  .object({
    organizationName: z.string().min(2, "Must be at least 2 characters").max(255),
    fullName: z.string().min(1, "Required").max(255),
    email: z.string().email("Enter a valid email address"),
    password: z.string().min(12, "Must be at least 12 characters").max(256),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ["confirmPassword"],
  });

export type RegisterFormValues = z.infer<typeof registerSchema>;

export const loginSchema = z.object({
  tenantSlug: z
    .string()
    .min(1, "Required")
    .max(63)
    .regex(/^[a-z0-9-]+$/, "Lowercase letters, numbers, and hyphens only"),
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Required"),
});

export type LoginFormValues = z.infer<typeof loginSchema>;
