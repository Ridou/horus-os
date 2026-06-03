"use client";

import { cn } from "@/lib/cn";

interface PageSkeletonProps {
  variant?: "list" | "detail" | "dashboard";
}

function Bar({ className }: { className?: string }) {
  return (
    <div className={cn("animate-pulse rounded-md bg-bg-elevated", className)} />
  );
}

/** Loading placeholder for the three page archetypes. */
export function PageSkeleton({ variant = "list" }: PageSkeletonProps) {
  if (variant === "dashboard") {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Bar key={i} className="h-24" />
          ))}
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Bar className="h-64" />
          <Bar className="h-64" />
        </div>
      </div>
    );
  }

  if (variant === "detail") {
    return (
      <div className="max-w-3xl space-y-6">
        <Bar className="h-9 w-2/3" />
        <Bar className="h-5 w-1/3" />
        <div className="flex gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Bar key={i} className="h-7 w-20" />
          ))}
        </div>
        <Bar className="h-48" />
        <Bar className="h-32" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Bar className="h-9 max-w-xs flex-1" />
        <Bar className="h-9 w-24" />
      </div>
      <div className="border border-border-subtle">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="flex items-center gap-3 border-b border-border-subtle px-4 py-3 last:border-b-0"
          >
            <Bar className="h-3 w-3 rounded-full" />
            <Bar className="h-4 flex-1" />
            <Bar className="h-5 w-16 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default PageSkeleton;
