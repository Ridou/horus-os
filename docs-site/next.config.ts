import type { NextConfig } from "next";

/**
 * Static-export configuration for the horus-os documentation site.
 *
 * The docs site is a fully static set of HTML, CSS, and JavaScript. There is no
 * Next.js server at runtime, so Vercel (or any static host) serves the contents
 * of `out/` directly. See DEPLOY.md for the Vercel project settings.
 */
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
