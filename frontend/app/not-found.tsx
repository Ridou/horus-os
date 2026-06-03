"use client";

import Link from "next/link";
import { Home } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <p className="text-5xl font-bold text-accent-cyan">404</p>
      <p className="mt-3 text-sm text-text-secondary">
        That page does not exist.
      </p>
      <Link
        href="/"
        className="mt-5 inline-flex items-center gap-1.5 border border-border-subtle px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-bg-elevated hover:text-text-primary"
      >
        <Home className="h-3.5 w-3.5" />
        Back home
      </Link>
    </div>
  );
}
