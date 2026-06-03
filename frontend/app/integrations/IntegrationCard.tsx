"use client";

import { StatusDot } from "@/components";
import type { IntegrationStatus } from "@/lib/types";

interface IntegrationCardProps {
  integration: IntegrationStatus;
  onViewWalkthrough: () => void;
}

export function IntegrationCard({
  integration,
  onViewWalkthrough,
}: IntegrationCardProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`${integration.name} - View walkthrough`}
      onClick={onViewWalkthrough}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onViewWalkthrough();
        }
      }}
      className="border border-border-subtle bg-bg-secondary p-4 border-glow min-h-[44px] cursor-pointer"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-bold text-text-primary">
          {integration.name}
        </span>
        <StatusDot
          state={integration.status}
          size="md"
          pulse={integration.status === "verified"}
        />
      </div>
      <p className="mt-1 text-xs text-text-secondary">{integration.description}</p>
      <span className="mt-2 block text-[10px] uppercase tracking-wider text-text-muted">
        {integration.category}
      </span>
      <span className="mt-4 inline-block rounded-sm bg-accent-cyan px-3 py-1 text-xs font-bold text-bg-primary">
        View walkthrough
      </span>
    </div>
  );
}
