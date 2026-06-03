"use client";

import { isDemoMode } from "@/lib/api";
import { DashboardHome } from "@/components/DashboardHome";
import { MarketingLanding } from "@/components/MarketingLanding";

/**
 * Root route.
 *
 * In demo mode (NEXT_PUBLIC_HORUS_DEMO === "1") "/" is the public marketing
 * landing, and the live dashboard is reached from "Launch the demo". A local,
 * non-demo install opens straight into the dashboard home with no marketing.
 *
 * `isDemoMode` is resolved at build time from the env var, so each static
 * export ships exactly one of the two as the root page.
 */
export default function HomePage() {
  return isDemoMode ? <MarketingLanding /> : <DashboardHome />;
}
