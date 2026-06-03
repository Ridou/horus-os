"use client";

import { cn } from "@/lib/cn";
import { statusStyle, statusLabel } from "@/lib/status-colors";

interface StatusBadgeProps {
  status: string;
  className?: string;
}

/** Rounded pill with semantic coloring backed by the generic status map. */
export function StatusBadge({ status, className }: StatusBadgeProps) {
  const style = statusStyle(status);
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium",
        style.badge,
        className,
      )}
    >
      {statusLabel(status)}
    </span>
  );
}

export default StatusBadge;
