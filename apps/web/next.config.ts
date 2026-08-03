import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  // `typedRoutes` was on but never actually verified — `npm run
  // typecheck` (plain `tsc --noEmit`) doesn't run the route-typing check
  // at all; only `next build` does, and nothing in this project's
  // verification loop ran a real build before deploying to Render. It
  // failed on two completely ordinary patterns (a data-driven nav array,
  // a redirect target read from `?next=`) that got fixed with explicit
  // `Route` typing/casts, but there was no cheap way to confirm there
  // weren't more without repeated slow round-trips through Render's
  // build. Off for now, as an experimental feature that wasn't pulling
  // its weight; revisit by re-enabling and running `next build` locally
  // (not just typecheck/lint/test) before trusting it again.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
