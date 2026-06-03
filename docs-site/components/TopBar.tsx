"use client";

import Link from "next/link";
import Image from "next/image";
import { Search, Menu } from "lucide-react";

const GITHUB_URL = "https://github.com/Ridou/horus-os";

/** Inline GitHub mark (lucide dropped the brand icon). */
function GithubMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className={className}
    >
      <path d="M12 2C6.48 2 2 6.58 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.1.68-.22.68-.49 0-.24-.01-.88-.01-1.73-2.78.62-3.37-1.37-3.37-1.37-.45-1.18-1.11-1.49-1.11-1.49-.91-.64.07-.62.07-.62 1 .07 1.53 1.06 1.53 1.06.89 1.56 2.34 1.11 2.91.85.09-.66.35-1.11.63-1.37-2.22-.26-4.55-1.14-4.55-5.06 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.3.1-2.71 0 0 .84-.27 2.75 1.05a9.36 9.36 0 0 1 2.5-.34c.85 0 1.71.12 2.5.34 1.91-1.32 2.75-1.05 2.75-1.05.55 1.41.2 2.45.1 2.71.64.72 1.03 1.63 1.03 2.75 0 3.93-2.34 4.79-4.57 5.05.36.32.68.94.68 1.9 0 1.37-.01 2.48-.01 2.82 0 .27.18.6.69.49A10.02 10.02 0 0 0 22 12.25C22 6.58 17.52 2 12 2Z" />
    </svg>
  );
}

export function TopBar({
  onOpenSearch,
  onToggleMenu,
}: {
  onOpenSearch: () => void;
  onToggleMenu: () => void;
}) {
  return (
    <header className="sticky top-0 z-40 flex h-16 items-center gap-3 border-b border-border-subtle bg-bg-primary/85 px-4 backdrop-blur-md sm:px-6">
      <button
        type="button"
        onClick={onToggleMenu}
        aria-label="Toggle navigation"
        className="rounded-md p-1.5 text-text-secondary transition-colors hover:bg-bg-elevated hover:text-text-primary lg:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      <Link href="/" className="flex items-center gap-2.5">
        <Image
          src="/horus-eye.svg"
          alt=""
          width={26}
          height={20}
          priority
          className="status-pulse"
        />
        <span className="text-[15px] font-bold tracking-tight text-text-primary">
          horus<span className="text-accent-cyan">-os</span>
        </span>
        <span className="hidden font-mono text-[11px] text-text-muted sm:inline">
          / docs
        </span>
      </Link>

      <div className="flex-1" />

      <button
        type="button"
        onClick={onOpenSearch}
        className="flex items-center gap-2 rounded-md border border-border-subtle bg-bg-secondary px-3 py-1.5 text-xs text-text-muted transition-colors hover:border-accent-cyan/40 hover:text-text-secondary"
      >
        <Search className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">Search docs</span>
        <kbd className="ml-1 hidden rounded border border-border-subtle px-1.5 py-0.5 font-mono text-[10px] sm:inline">
          ⌘K
        </kbd>
      </button>

      <a
        href={GITHUB_URL}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="horus-os on GitHub"
        className="rounded-md p-1.5 text-text-secondary transition-colors hover:bg-bg-elevated hover:text-text-primary"
      >
        <GithubMark className="h-5 w-5" />
      </a>
    </header>
  );
}
