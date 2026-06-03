"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";

/** A copy-to-clipboard button for a command string. */
export function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard may be unavailable (insecure context). Fail quietly.
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      aria-label={copied ? "Copied" : "Copy command"}
      className="inline-flex shrink-0 items-center gap-1.5 rounded-sm border border-border-subtle bg-bg-elevated px-2 py-1 text-[11px] font-bold text-text-secondary transition-colors hover:border-accent-cyan/40 hover:text-accent-cyan"
    >
      {copied ? (
        <>
          <Check className="h-3 w-3 text-success" />
          Copied
        </>
      ) : (
        <>
          <Copy className="h-3 w-3" />
          Copy
        </>
      )}
    </button>
  );
}
