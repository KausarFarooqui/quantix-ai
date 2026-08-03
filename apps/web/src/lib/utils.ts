import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind class lists safely, resolving conflicting utility
 * classes (e.g. `p-2` vs `p-4`) in favor of the last one specified.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
