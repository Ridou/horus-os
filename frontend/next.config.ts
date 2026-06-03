import type { NextConfig } from "next";

/**
 * Static-export configuration.
 *
 * The dashboard is bundled into a Python wheel and served as plain static
 * files by the FastAPI runtime (mounted at "/"). The marketing demo is served
 * the same way. There is no Next.js server in production, so every page must
 * be a client-rendered component that fetches data at runtime.
 */
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
  // Default basePath: the export is served at the site root in every target.
};

export default nextConfig;
