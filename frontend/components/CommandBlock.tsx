"use client";

import { CopyButton } from "./CopyButton";

/** A monospace command line with an inline copy button. */
export function CommandBlock({ command }: { command: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border border-border-subtle bg-bg-primary px-3 py-2.5">
      <code className="overflow-x-auto whitespace-nowrap text-[13px] text-accent-cyan scrollbar-none">
        <span className="select-none text-text-muted">$ </span>
        {command}
      </code>
      <CopyButton value={command} />
    </div>
  );
}
