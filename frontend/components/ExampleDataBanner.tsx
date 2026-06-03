"use client";

import { useState } from "react";
import { FlaskConical, X } from "lucide-react";

interface ExampleDataBannerProps {
  showClear?: boolean;
  onClear?: () => void | Promise<void>;
  onDismiss?: () => void;
}

export function ExampleDataBanner({
  showClear = false,
  onClear,
  onDismiss,
}: ExampleDataBannerProps) {
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <div>
      <div className="flex items-center gap-3 border-l-2 border-accent-cyan bg-accent-cyan/5 px-4 py-3 mb-4 text-sm">
        <FlaskConical className="h-4 w-4 text-accent-cyan shrink-0" />
        <span>
          <span className="font-bold text-text-primary">Example data</span>
          <span className="text-text-secondary ml-1">
            This content was seeded automatically and is safe to clear.
          </span>
        </span>
        {showClear && (
          <button
            type="button"
            onClick={() => {
              setConfirming(true);
              setError(null);
            }}
            className="ml-auto shrink-0 border border-danger/40 px-3 py-2 text-xs font-bold text-danger hover:bg-danger/10 transition-colors"
          >
            Clear demo data
          </button>
        )}
        {!showClear && (
          <button
            type="button"
            aria-label="Dismiss example data banner"
            onClick={onDismiss}
            className="ml-2 text-text-muted hover:text-text-primary"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      {confirming && (
        <div className="flex items-center gap-3 border border-danger/30 bg-danger/5 px-4 py-3 text-xs mb-4">
          <span className="text-text-secondary">
            This will permanently delete the demo trace. Are you sure?
          </span>
          <button
            type="button"
            className="ml-auto bg-danger text-white font-bold px-3 py-2 text-xs"
            onClick={async () => {
              try {
                await onClear?.();
                setConfirming(false);
                setError(null);
              } catch {
                setError("Could not clear demo data. Try again.");
              }
            }}
          >
            Delete demo trace
          </button>
          <button
            type="button"
            className="text-text-secondary hover:text-text-primary"
            onClick={() => setConfirming(false)}
          >
            Keep it
          </button>
        </div>
      )}
      {error && <p className="text-xs text-danger mb-4">{error}</p>}
    </div>
  );
}
