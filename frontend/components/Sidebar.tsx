"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  Home,
  MessageSquare,
  Users,
  Store,
  Brain,
  CheckSquare,
  Telescope,
  Activity,
  Network,
  DollarSign,
  Plug,
  Settings,
  Info,
  BookText,
  X,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { isDemoMode } from "@/lib/api";
import { useIsDesktop } from "@/lib/use-is-desktop";

/** Public community Discord invite. */
const DISCORD_URL = "https://discord.gg/vwX9WvwQhp";

/** Canonical documentation site. */
const DOCS_URL = "https://docs.horus-demo.com";

/** Inline Discord mark (lucide-react ships no brand icons). */
function DiscordMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className={className}
    >
      <path d="M20.317 4.3698a19.7913 19.7913 0 0 0-4.8851-1.5152.0741.0741 0 0 0-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 0 0-.0785-.037 19.7363 19.7363 0 0 0-4.8852 1.515.0699.0699 0 0 0-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 0 0 .0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 0 0 .0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 0 0-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 0 1-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 0 1 .0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 0 1 .0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 0 1-.0066.1276 12.2986 12.2986 0 0 1-1.873.8914.0766.0766 0 0 0-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 0 0 .0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 0 0 .0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 0 0-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z" />
    </svg>
  );
}

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Home", icon: Home },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/team", label: "Team", icon: Users },
  { href: "/store", label: "Store", icon: Store },
  { href: "/memory", label: "Memory", icon: Brain },
  { href: "/tasks", label: "Tasks", icon: CheckSquare },
  { href: "/research", label: "Research", icon: Telescope },
  { href: "/activity", label: "Activity", icon: Activity },
  { href: "/traces", label: "Traces", icon: Network },
  { href: "/costs", label: "Costs", icon: DollarSign },
  { href: "/integrations", label: "Integrations", icon: Plug },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/about", label: "About", icon: Info },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

interface SidebarProps {
  /**
   * Whether the mobile drawer is open. Ignored at the md breakpoint and up,
   * where the sidebar is always a persistent static column.
   */
  open?: boolean;
  /**
   * Called when a nav link or the close control is activated, so the parent
   * can dismiss the mobile drawer. No-op on desktop.
   */
  onNavigate?: () => void;
}

export function Sidebar({ open = false, onNavigate }: SidebarProps) {
  const pathname = usePathname();
  const isDesktop = useIsDesktop();
  // On mobile the closed drawer is only translated off-screen, which leaves its
  // links in the tab order and the accessibility tree. Mark it inert so keyboard
  // and screen-reader users do not land on invisible controls. The desktop
  // column (and the open drawer) stay fully interactive.
  const collapsed = !isDesktop && !open;

  return (
    <aside
      id="app-sidebar"
      aria-label="Primary"
      aria-hidden={collapsed || undefined}
      inert={collapsed || undefined}
      className={cn(
        // Mobile: fixed off-canvas drawer that slides in from the left.
        "fixed inset-y-0 left-0 z-40 flex h-full w-64 shrink-0 flex-col border-r border-border-subtle bg-bg-secondary transition-transform duration-200 ease-out",
        // Desktop: persistent static column, always on screen.
        "md:static md:z-auto md:w-56 md:translate-x-0 md:transition-none",
        open ? "translate-x-0" : "-translate-x-full",
      )}
    >
      {/* Logo + wordmark, with a close control on mobile */}
      <div className="flex items-center justify-between border-b border-border-subtle px-4 py-4">
        <Link
          href="/"
          onClick={onNavigate}
          className="flex items-center gap-2.5"
        >
          <Image
            src="/horus-eye.svg"
            alt="horus-os"
            width={28}
            height={21}
            priority
            className="status-pulse"
          />
          <span className="text-base font-bold tracking-tight text-text-primary">
            horus<span className="text-accent-cyan">-os</span>
          </span>
        </Link>
        <button
          type="button"
          onClick={onNavigate}
          aria-label="Close navigation menu"
          className="-mr-1 inline-flex min-h-11 min-w-11 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-bg-elevated hover:text-text-primary md:hidden"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
        {NAV_ITEMS.map((item) => {
          const active = isActive(pathname, item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-bold transition-colors",
                active
                  ? "bg-accent-cyan/10 text-accent-cyan"
                  : "text-text-secondary hover:bg-bg-elevated hover:text-text-primary",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="flex flex-col gap-2 border-t border-border-subtle px-4 py-3 text-xs text-text-muted">
        {isDemoMode ? (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-accent-cyan" />
            Demo mode
          </span>
        ) : (
          <span>Local instance</span>
        )}
        <a
          href={DOCS_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 transition-colors hover:text-accent-cyan"
        >
          <BookText className="h-3.5 w-3.5 shrink-0" />
          Docs
        </a>
        <a
          href={DISCORD_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 transition-colors hover:text-accent-cyan"
        >
          <DiscordMark className="h-3.5 w-3.5 shrink-0" />
          Community
        </a>
      </div>
    </aside>
  );
}

export default Sidebar;
