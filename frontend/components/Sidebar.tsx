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
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { isDemoMode } from "@/lib/api";

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

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-border-subtle bg-bg-secondary">
      {/* Logo + wordmark */}
      <Link
        href="/"
        className="flex items-center gap-2.5 border-b border-border-subtle px-4 py-4"
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

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
        {NAV_ITEMS.map((item) => {
          const active = isActive(pathname, item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
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
      <div className="border-t border-border-subtle px-4 py-3 text-xs text-text-muted">
        {isDemoMode ? (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-accent-cyan" />
            Demo mode
          </span>
        ) : (
          <span>Local instance</span>
        )}
      </div>
    </aside>
  );
}

export default Sidebar;
