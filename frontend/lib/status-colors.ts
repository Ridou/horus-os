import type { AgentStatus } from "./types";

/**
 * Generic status color system for the dashboard. Eight canonical keys cover
 * the agent lifecycle plus trace and task outcomes.
 *
 *  - dot:   hex color for a small status dot.
 *  - badge: pill background + text classes (cyan-on-near-black friendly).
 *  - ring:  border + text classes for outline-style icons.
 *  - pulse: whether the indicator should animate (live states).
 */

export interface StatusStyle {
  label: string;
  dot: string;
  badge: string;
  ring: string;
  pulse: boolean;
}

export const STATUS_STYLES: Record<string, StatusStyle> = {
  active: {
    label: "Active",
    dot: "#22c55e",
    badge: "bg-green-500/10 text-green-400",
    ring: "border-green-400 text-green-400",
    pulse: false,
  },
  running: {
    label: "Running",
    dot: "#00d4ff",
    badge: "bg-cyan-500/10 text-cyan-300",
    ring: "border-cyan-400 text-cyan-300",
    pulse: true,
  },
  paused: {
    label: "Paused",
    dot: "#f59e0b",
    badge: "bg-amber-500/10 text-amber-400",
    ring: "border-amber-400 text-amber-400",
    pulse: false,
  },
  idle: {
    label: "Idle",
    dot: "#9ca3af",
    badge: "bg-neutral-500/10 text-neutral-400",
    ring: "border-neutral-400 text-neutral-400",
    pulse: false,
  },
  done: {
    label: "Done",
    dot: "#22c55e",
    badge: "bg-green-500/10 text-green-400",
    ring: "border-green-400 text-green-400",
    pulse: false,
  },
  pending: {
    label: "Pending",
    dot: "#f59e0b",
    badge: "bg-yellow-500/10 text-yellow-400",
    ring: "border-yellow-400 text-yellow-400",
    pulse: false,
  },
  error: {
    label: "Error",
    dot: "#ef4444",
    badge: "bg-red-500/10 text-red-400",
    ring: "border-red-400 text-red-400",
    pulse: false,
  },
  blocked: {
    label: "Blocked",
    dot: "#ef4444",
    badge: "bg-red-500/10 text-red-400",
    ring: "border-red-400 text-red-400",
    pulse: false,
  },
};

export const STATUS_STYLE_DEFAULT: StatusStyle = {
  label: "Unknown",
  dot: "#6b7280",
  badge: "bg-neutral-500/10 text-neutral-400",
  ring: "border-neutral-500 text-neutral-500",
  pulse: false,
};

/** Resolve a status string to its style, with a safe fallback. */
export function statusStyle(status: string): StatusStyle {
  return STATUS_STYLES[status] ?? STATUS_STYLE_DEFAULT;
}

/** Display label for a status (title-cased fallback for unknown keys). */
export function statusLabel(status: string): string {
  const known = STATUS_STYLES[status];
  if (known) return known.label;
  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Ordered list of agent statuses for sorting (live states first). */
const STATUS_ORDER: Record<string, number> = {
  running: 0,
  active: 1,
  pending: 2,
  paused: 3,
  idle: 4,
  blocked: 5,
  error: 6,
  done: 7,
};

export function statusOrder(status: string): number {
  return STATUS_ORDER[status] ?? 99;
}

export type { AgentStatus };
