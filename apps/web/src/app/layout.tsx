import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { AppProviders } from "@/app/providers";
import "@/styles/globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: {
    default: "Quantix AI",
    template: "%s · Quantix AI",
  },
  description:
    "AI-powered analytics platform — connect data, ask questions in plain English, forecast trends, and ship executive reports.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans`}>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
