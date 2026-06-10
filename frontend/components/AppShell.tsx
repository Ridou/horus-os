"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import Image from "next/image";
import { ArrowRight, Menu } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { cn } from "@/lib/cn";
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

/**
 * App frame: a persistent left sidebar on desktop that collapses into a
 * hamburger-triggered drawer on mobile, plus a scrollable content column.
 */
export function AppShell({ children }: AppShellProps) {
  const [navOpen, setNavOpen] = useState(false);

  // In-app navigation closes the drawer through the nav links' onNavigate
  // handler; while open, the backdrop covers all other content, so no other
  // tap can change the route without first dismissing the drawer.

  // Close the drawer once the viewport grows to the persistent-sidebar
  // breakpoint, so an open drawer never lingers as a desktop scroll lock.
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const mq = window.matchMedia("(min-width: 768px)");
    const onChange = () => {
      if (mq.matches) setNavOpen(false);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  // While the drawer is open, close on Escape and lock background scroll.
  useEffect(() => {
    if (!navOpen) return;

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setNavOpen(false);
    };
    document.addEventListener("keydown", onKey);

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [navOpen]);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile drawer backdrop: fades in/out in lockstep with the drawer slide. */}
      <div
        aria-hidden="true"
        onClick={() => setNavOpen(false)}
        className={cn(
          "fixed inset-0 z-30 bg-bg-primary/75 backdrop-blur-sm transition-opacity duration-200 ease-out md:hidden",
          navOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />

      <Sidebar open={navOpen} onNavigate={() => setNavOpen(false)} />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile top bar; hidden once the sidebar is persistent at md+. */}
        <header className="flex items-center gap-3 border-b border-border-subtle bg-bg-secondary px-4 py-3 md:hidden">
          <button
            type="button"
            onClick={() => setNavOpen(true)}
            aria-label="Open navigation menu"
            aria-expanded={navOpen}
            aria-controls="app-sidebar"
            className="-ml-1 inline-flex min-h-11 min-w-11 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-bg-elevated hover:text-text-primary"
          >
            <Menu className="h-5 w-5" />
          </button>
          <Link href="/" className="flex items-center gap-2">
            <Image
              src="/horus-eye.svg"
              alt=""
              width={24}
              height={18}
              priority
            />
            <span className="text-base font-bold tracking-tight text-text-primary">
              horus<span className="text-accent-cyan">-os</span>
            </span>
          </Link>
        </header>

        <main className="flex-1 overflow-y-auto">
          {isDemoMode && <DemoBanner />}
          <div className="mx-auto max-w-6xl p-4 md:p-6 animate-fade-in">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

export default AppShell;
