"use client";

import { cn } from "@/lib/cn";
import { statusStyle } from "@/lib/status-colors";

interface StatusIconProps {
  status: string;
  className?: string;
}

/**
 * Status indicator dot. Live states (running) pulse; terminal states render a
 * solid dot inside a colored ring.
 */
export function StatusIcon({ status, className }: StatusIconProps) {
  const style = statusStyle(status);
  return (
    <span className={cn("relative inline-flex h-2.5 w-2.5 shrink-0", className)}>
      {style.pulse && (
        <span
          className="absolute inline-flex h-full w-full animate-pulse rounded-full opacity-75"
          style={{ backgroundColor: style.dot }}
        />
      )}
      <span
        className="relative inline-flex h-2.5 w-2.5 rounded-full"
        style={{ backgroundColor: style.dot }}
      />
    </span>
  );
}

export default StatusIcon;
