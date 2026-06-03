"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { isDemoMode } from "@/lib/api";

interface AppShellProps {
  children: ReactNode;
}

/** Slim sticky banner shown only in demo mode, inviting a real install. */
function DemoBanner() {
  return (
    <div className="sticky top-0 z-20 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 border-b border-accent-cyan/20 bg-accent-cyan/10 px-4 py-2 text-center text-xs text-text-secondary backdrop-blur">
      <span>
        You are viewing a live demo with sample data. Install horus-os to run
        your own agents with your own keys.
      </span>
      <Link
        href="/get-started/"
        className="inline-flex items-center gap-1 font-bold text-accent-cyan transition-colors hover:underline"
      >
        Get started
        <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}

/** App frame: persistent left sidebar plus a scrollable content column. */
export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        {isDemoMode && <DemoBanner />}
        <div className="mx-auto max-w-6xl p-4 md:p-6 animate-fade-in">
          {children}
        </div>
      </main>
    </div>
  );
}

export default AppShell;
