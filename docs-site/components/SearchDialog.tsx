"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, FileText, CornerDownLeft } from "lucide-react";
import { cn } from "@/lib/cn";

interface SearchRecord {
  slug: string;
  title: string;
  description: string;
  headings: string[];
  body: string;
}

function sectionLabel(slug: string): string {
  const parts = slug.split("/");
  return parts.length > 1 ? parts[0].replace(/-/g, " ") : "";
}

function score(rec: SearchRecord, terms: string[]): number {
  let total = 0;
  const title = rec.title.toLowerCase();
  const desc = rec.description.toLowerCase();
  const heads = rec.headings.join(" ").toLowerCase();
  const body = rec.body.toLowerCase();
  for (const t of terms) {
    if (!t) continue;
    if (title.includes(t)) total += 6;
    if (heads.includes(t)) total += 3;
    if (desc.includes(t)) total += 2;
    if (body.includes(t)) total += 1;
  }
  return total;
}

export function SearchDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const [records, setRecords] = useState<SearchRecord[] | null>(null);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open && records === null) {
      fetch("/search-index.json")
        .then((r) => r.json())
        .then((data: SearchRecord[]) => setRecords(data))
        .catch(() => setRecords([]));
    }
  }, [open, records]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setCursor(0);
      const id = window.setTimeout(() => inputRef.current?.focus(), 20);
      return () => window.clearTimeout(id);
    }
  }, [open]);

  const results = useMemo(() => {
    if (!records || !query.trim()) return [];
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    return records
      .map((rec) => ({ rec, s: score(rec, terms) }))
      .filter((x) => x.s > 0)
      .sort((a, b) => b.s - a.s)
      .slice(0, 8)
      .map((x) => x.rec);
  }, [records, query]);

  useEffect(() => setCursor(0), [query]);

  function go(rec: SearchRecord) {
    onClose();
    router.push(`/${rec.slug}/`);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((c) => Math.min(c + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => Math.max(c - 1, 0));
    } else if (e.key === "Enter" && results[cursor]) {
      e.preventDefault();
      go(results[cursor]);
    }
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 p-4 pt-[12vh] backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-lg border border-border-subtle bg-bg-secondary shadow-2xl glow-cyan animate-fade-in"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Search documentation"
      >
        <div className="flex items-center gap-3 border-b border-border-subtle px-4">
          <Search className="h-4 w-4 shrink-0 text-text-muted" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search the docs..."
            className="w-full bg-transparent py-4 font-mono text-sm text-text-primary outline-none placeholder:text-text-muted"
          />
          <kbd className="hidden shrink-0 rounded border border-border-subtle px-1.5 py-0.5 font-mono text-[10px] text-text-muted sm:block">
            ESC
          </kbd>
        </div>

        <div className="max-h-[55vh] overflow-y-auto p-2">
          {query.trim() === "" ? (
            <p className="px-3 py-8 text-center font-mono text-xs text-text-muted">
              Type to search across every page.
            </p>
          ) : results.length === 0 ? (
            <p className="px-3 py-8 text-center font-mono text-xs text-text-muted">
              No results for &ldquo;{query}&rdquo;.
            </p>
          ) : (
            <ul>
              {results.map((rec, i) => {
                const sect = sectionLabel(rec.slug);
                return (
                  <li key={rec.slug}>
                    <button
                      type="button"
                      onMouseEnter={() => setCursor(i)}
                      onClick={() => go(rec)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left transition-colors",
                        i === cursor ? "bg-accent-cyan/10" : "hover:bg-bg-elevated",
                      )}
                    >
                      <FileText
                        className={cn(
                          "h-4 w-4 shrink-0",
                          i === cursor ? "text-accent-cyan" : "text-text-muted",
                        )}
                      />
                      <span className="min-w-0 flex-1">
                        <span
                          className={cn(
                            "block truncate text-sm font-bold",
                            i === cursor ? "text-accent-cyan" : "text-text-primary",
                          )}
                        >
                          {rec.title}
                        </span>
                        {(sect || rec.description) && (
                          <span className="block truncate text-xs text-text-muted">
                            {sect && (
                              <span className="capitalize">{sect}</span>
                            )}
                            {sect && rec.description && " · "}
                            {rec.description}
                          </span>
                        )}
                      </span>
                      {i === cursor && (
                        <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-accent-cyan" />
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
