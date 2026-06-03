"use client";

import type { IntegrationStatus } from "@/lib/types";

interface ReadinessSummaryProps {
  integrations: IntegrationStatus[];
}

export function ReadinessSummary({ integrations }: ReadinessSummaryProps) {
  const readyCount = integrations.filter(
    (i) => i.status === "verified" || i.status === "configured-unverified",
  ).length;
  const total = integrations.length;

  return (
    <div className="mb-6 flex items-center gap-2 text-sm text-text-secondary">
      {readyCount === 0 ? (
        <span>
          <span className="font-bold text-accent-cyan tabular-nums">0</span>
          {" "}of {total} integrations ready - add at least one API key to get started
        </span>
      ) : (
        <span>
          <span className="font-bold text-accent-cyan tabular-nums">{readyCount}</span>
          {" "}of {total} integrations ready
        </span>
      )}
    </div>
  );
}
