"use client";

import { useEffect, useState } from "react";
import type { TocItem } from "@/lib/content";
import { cn } from "@/lib/cn";

/** "On this page" rail with scroll-spy active highlighting. */
export function TableOfContents({ toc }: { toc: TocItem[] }) {
  const [active, setActive] = useState<string>("");

  useEffect(() => {
    if (toc.length === 0) return;
    const headings = toc
      .map((t) => document.getElementById(t.id))
      .filter((el): el is HTMLElement => el !== null);

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-80px 0px -70% 0px", threshold: [0, 1] },
    );

    headings.forEach((h) => observer.observe(h));
    return () => observer.disconnect();
  }, [toc]);

  if (toc.length === 0) return null;

  return (
    <div className="sticky top-20 max-h-[calc(100vh-6rem)] overflow-y-auto py-10 pr-4 scrollbar-none">
      <p className="mb-3 text-[11px] font-bold uppercase tracking-wider text-text-muted">
        On this page
      </p>
      <ul className="space-y-1.5 border-l border-border-subtle">
        {toc.map((item) => (
          <li key={item.id}>
            <a
              href={`#${item.id}`}
              className={cn(
                "block border-l -ml-px py-0.5 text-[12.5px] leading-snug transition-colors",
                item.depth === 3 ? "pl-6" : "pl-3",
                active === item.id
                  ? "border-accent-cyan text-accent-cyan"
                  : "border-transparent text-text-muted hover:text-text-secondary",
              )}
            >
              {item.text}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
