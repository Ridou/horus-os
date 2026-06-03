"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Rocket,
  Boxes,
  BookOpen,
  Plug,
  Puzzle,
  Server,
  FileCode,
  Users,
  ChevronDown,
  type LucideIcon,
} from "lucide-react";
import { NAV } from "@/lib/nav";
import { cn } from "@/lib/cn";

const ICONS: Record<string, LucideIcon> = {
  Rocket,
  Boxes,
  BookOpen,
  Plug,
  Puzzle,
  Server,
  FileCode,
  Users,
};

function normalize(p: string): string {
  return p.replace(/\/+$/, "") || "/";
}

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = normalize(usePathname());
  const activeSection = NAV.find((s) =>
    s.items.some((i) => `/${i.slug}` === pathname),
  )?.label;

  return (
    <nav className="space-y-6 px-3 py-6">
      {NAV.map((section) => (
        <Section
          key={section.label}
          label={section.label}
          icon={ICONS[section.icon]}
          defaultOpen={section.label === activeSection || true}
        >
          {section.items.map((item) => {
            const href = `/${item.slug}`;
            const active = href === pathname;
            return (
              <Link
                key={item.slug}
                href={`/${item.slug}/`}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "block border-l border-border-subtle py-1.5 pl-4 text-[13px] transition-colors",
                  active
                    ? "border-accent-cyan font-bold text-accent-cyan"
                    : "text-text-secondary hover:border-text-muted hover:text-text-primary",
                )}
              >
                {item.title}
              </Link>
            );
          })}
        </Section>
      ))}
    </nav>
  );
}

function Section({
  label,
  icon: Icon,
  defaultOpen,
  children,
}: {
  label: string;
  icon?: LucideIcon;
  defaultOpen: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="mb-1 flex w-full items-center gap-2 px-1 text-[11px] font-bold uppercase tracking-wider text-text-muted transition-colors hover:text-text-secondary"
      >
        {Icon && <Icon className="h-3.5 w-3.5 text-accent-cyan/70" />}
        <span className="flex-1 text-left">{label}</span>
        <ChevronDown
          className={cn("h-3.5 w-3.5 transition-transform", !open && "-rotate-90")}
        />
      </button>
      {open && <div className="ml-1.5">{children}</div>}
    </div>
  );
}
