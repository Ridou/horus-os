"use client";

import { useEffect, useMemo, useState } from "react";
import { Brain, Search, Star, FileText } from "lucide-react";
import { useMemory, useMemoryNote } from "@/lib/hooks";
import { cn } from "@/lib/cn";
import { timeAgo } from "@/lib/time";
import { useTabParam } from "@/lib/use-tab-param";
import type { MemoryNote } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { PageSkeleton } from "@/components/PageSkeleton";
import { EmptyState } from "@/components/EmptyState";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { ExampleDataBanner } from "@/components";

/** Slug of the curated welcome note, pinned as a featured callout. */
const WELCOME_PATH = "notes/welcome-to-horus-os.md";

/** Debounce a fast-changing value so search does not refetch on every keypress. */
function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

function NoteRow({
  note,
  selected,
  onSelect,
}: {
  note: MemoryNote;
  selected: boolean;
  onSelect: (path: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(note.path)}
      className={cn(
        "flex w-full flex-col gap-1 border-b border-border-subtle px-4 py-3 text-left transition-colors last:border-b-0",
        selected
          ? "bg-accent-cyan/10"
          : "hover:bg-bg-elevated/60",
      )}
    >
      <div className="flex items-center gap-2">
        <FileText className="h-3.5 w-3.5 shrink-0 text-text-muted" />
        <span className="flex-1 truncate text-sm font-medium text-text-primary">
          {note.title}
        </span>
        <span className="shrink-0 text-[10px] text-text-muted tabular-nums">
          {timeAgo(note.modified_at)}
        </span>
      </div>
      <p className="line-clamp-2 pl-5 text-xs text-text-secondary">
        {note.preview}
      </p>
    </button>
  );
}

export default function MemoryPage() {
  const [selectedPath, setSelectedPath] = useTabParam<string>("note", "");
  const [rawQuery, setRawQuery] = useState("");
  const query = useDebounced(rawQuery, 300);

  const { data, isLoading } = useMemory(query);
  const notes = useMemo(() => data?.notes ?? [], [data]);

  const welcome = useMemo(
    () => notes.find((n) => n.path === WELCOME_PATH),
    [notes],
  );
  const otherNotes = useMemo(
    () => notes.filter((n) => n.path !== WELCOME_PATH),
    [notes],
  );

  const selected = selectedPath || null;
  const { data: noteDetail, isLoading: noteLoading } = useMemoryNote(selected);

  const select = (path: string) =>
    setSelectedPath(path === selected ? "" : path);

  return (
    <div>
      <PageHeader
        title="Memory"
        description="Browse and search the notes your agents read and write. Everything lives as plain markdown."
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,360px)_1fr]">
        {/* Left: search + list */}
        <div className="flex flex-col">
          <div className="relative mb-3">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
            <input
              type="search"
              value={rawQuery}
              onChange={(e) => setRawQuery(e.target.value)}
              placeholder="Search notes"
              aria-label="Search notes"
              className="w-full border border-border-subtle bg-bg-secondary py-2 pl-9 pr-3 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-cyan focus:outline-none"
            />
          </div>

          {/* Pinned welcome callout */}
          {welcome && (
            <button
              type="button"
              onClick={() => select(welcome.path)}
              className={cn(
                "mb-3 flex flex-col gap-1 border-l-2 border-accent-cyan bg-bg-secondary p-3 text-left transition-colors gradient-cyber",
                selected === welcome.path
                  ? "ring-1 ring-accent-cyan"
                  : "hover:bg-bg-elevated/60",
              )}
            >
              <div className="flex items-center gap-2">
                <Star className="h-3.5 w-3.5 shrink-0 text-accent-cyan" />
                <span className="flex-1 truncate text-sm font-semibold text-text-primary">
                  {welcome.title}
                </span>
                <span className="shrink-0 rounded-full bg-accent-cyan/15 px-2 py-0.5 text-[9px] font-medium uppercase tracking-wider text-accent-cyan">
                  Start here
                </span>
              </div>
              <p className="line-clamp-2 text-xs text-text-secondary">
                {welcome.preview}
              </p>
            </button>
          )}

          {isLoading ? (
            <PageSkeleton variant="list" />
          ) : notes.length === 0 ? (
            <EmptyState
              icon={Brain}
              message={
                query
                  ? "No notes match your search."
                  : "No notes yet. Your agents will fill this in as they work."
              }
            />
          ) : (
            <div data-tour-step="3" className="border border-border-subtle bg-bg-secondary">
              {otherNotes.map((note) => (
                <NoteRow
                  key={note.path}
                  note={note}
                  selected={selected === note.path}
                  onSelect={select}
                />
              ))}
              {otherNotes.length === 0 && welcome && (
                <p className="px-4 py-6 text-center text-xs text-text-muted">
                  Only the welcome note matches. Clear the search to see more.
                </p>
              )}
            </div>
          )}
        </div>

        {/* Right: rendered note */}
        <div className="min-w-0 border border-border-subtle bg-bg-secondary">
          {!selected ? (
            <EmptyState
              icon={FileText}
              message="Select a note to read it here."
            />
          ) : noteLoading ? (
            <div className="p-5">
              <PageSkeleton variant="detail" />
            </div>
          ) : noteDetail ? (
            <article className="p-5">
              {noteDetail.is_example && (
                <ExampleDataBanner showClear={false} />
              )}
              <header className="mb-4 border-b border-border-subtle pb-3">
                <h2 className="text-lg font-bold text-text-primary">
                  {noteDetail.title}
                </h2>
                <p className="mt-1 flex items-center gap-2 text-[11px] text-text-muted">
                  <span className="font-mono">{noteDetail.path}</span>
                  <span>-</span>
                  <span>updated {timeAgo(noteDetail.modified_at)}</span>
                </p>
              </header>
              <MarkdownRenderer
                content={noteDetail.markdown}
                searchQuery={query}
                onNavigate={(name) => {
                  const match = notes.find(
                    (n) =>
                      n.title.toLowerCase() === name.toLowerCase() ||
                      n.path.toLowerCase().includes(name.toLowerCase()),
                  );
                  if (match) select(match.path);
                }}
              />
            </article>
          ) : (
            <EmptyState
              icon={FileText}
              message="Could not load this note."
            />
          )}
        </div>
      </div>
    </div>
  );
}
