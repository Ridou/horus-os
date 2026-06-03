"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { X } from "lucide-react";
import { TopBar } from "./TopBar";
import { SidebarNav } from "./SidebarNav";
import { SearchDialog } from "./SearchDialog";
import { cn } from "@/lib/cn";

export function DocsShell({ children }: { children: React.ReactNode }) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const pathname = usePathname();

  // Close the mobile drawer on route change.
  useEffect(() => setMenuOpen(false), [pathname]);

  // Global shortcuts: cmd/ctrl-K to search, ESC to close.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
      } else if (e.key === "Escape") {
        setSearchOpen(false);
        setMenuOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <TopBar
        onOpenSearch={() => setSearchOpen(true)}
        onToggleMenu={() => setMenuOpen((o) => !o)}
      />

      <div className="mx-auto flex w-full max-w-[88rem]">
        {/* Desktop sidebar */}
        <aside className="sticky top-16 hidden h-[calc(100vh-4rem)] w-64 shrink-0 overflow-y-auto border-r border-border-subtle scrollbar-none lg:block">
          <SidebarNav />
        </aside>

        {/* Mobile drawer */}
        {menuOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div
              className="absolute inset-0 bg-black/70 backdrop-blur-sm"
              onClick={() => setMenuOpen(false)}
            />
            <aside className="absolute left-0 top-0 h-full w-72 max-w-[85vw] overflow-y-auto border-r border-border-subtle bg-bg-secondary">
              <div className="flex h-16 items-center justify-between border-b border-border-subtle px-4">
                <span className="text-sm font-bold text-text-primary">
                  horus<span className="text-accent-cyan">-os</span> docs
                </span>
                <button
                  type="button"
                  onClick={() => setMenuOpen(false)}
                  aria-label="Close navigation"
                  className="rounded-md p-1.5 text-text-secondary hover:bg-bg-elevated"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <SidebarNav onNavigate={() => setMenuOpen(false)} />
            </aside>
          </div>
        )}

        {/* Content */}
        <main className={cn("min-w-0 flex-1")}>{children}</main>
      </div>

      <SearchDialog open={searchOpen} onClose={() => setSearchOpen(false)} />
    </>
  );
}
