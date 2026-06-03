import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import type { NavItem } from "@/lib/nav";

/** Previous / next page links at the foot of an article. */
export function Pagination({
  prev,
  next,
}: {
  prev: NavItem | null;
  next: NavItem | null;
}) {
  if (!prev && !next) return null;
  return (
    <nav className="mt-14 grid grid-cols-1 gap-3 border-t border-border-subtle pt-6 sm:grid-cols-2">
      {prev ? (
        <Link
          href={`/${prev.slug}/`}
          className="group flex flex-col gap-1 rounded-md border border-border-subtle p-4 transition-colors hover:border-accent-cyan/40 hover:bg-bg-secondary"
        >
          <span className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-text-muted">
            <ArrowLeft className="h-3 w-3" /> Previous
          </span>
          <span className="text-sm font-bold text-text-primary group-hover:text-accent-cyan">
            {prev.title}
          </span>
        </Link>
      ) : (
        <span />
      )}
      {next ? (
        <Link
          href={`/${next.slug}/`}
          className="group flex flex-col items-end gap-1 rounded-md border border-border-subtle p-4 text-right transition-colors hover:border-accent-cyan/40 hover:bg-bg-secondary"
        >
          <span className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-text-muted">
            Next <ArrowRight className="h-3 w-3" />
          </span>
          <span className="text-sm font-bold text-text-primary group-hover:text-accent-cyan">
            {next.title}
          </span>
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );
}
