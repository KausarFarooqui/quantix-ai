import { redirect } from "next/navigation";

/**
 * There's no marketing/login landing page in this build — visitors go
 * straight into the app shell, which silently establishes a demo session
 * (see `app/(app)/layout.tsx` and ADR-0008) before rendering anything.
 */
export default function RootPage(): never {
  redirect("/home");
}
