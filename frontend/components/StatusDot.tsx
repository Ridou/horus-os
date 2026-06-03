export type StatusDotState =
  | "verified"
  | "configured-unverified"
  | "missing"
  | "error";

interface StatusDotProps {
  state: StatusDotState;
  /** Activates the two-layer pulse animation when true. Default: false. */
  pulse?: boolean;
  /** sm = h-2 w-2 (8px), md = h-2.5 w-2.5 (10px). Default: md. */
  size?: "sm" | "md";
  /** Overrides the default aria-label for the state. */
  label?: string;
}

const bgClass: Record<StatusDotState, string> = {
  verified: "bg-success",
  "configured-unverified": "bg-warning",
  missing: "bg-text-muted",
  error: "bg-danger",
};

const defaultLabel: Record<StatusDotState, string> = {
  verified: "Verified",
  "configured-unverified": "Configured, verification pending",
  missing: "Not configured",
  error: "Configuration error",
};

const sizeClass: Record<NonNullable<StatusDotProps["size"]>, string> = {
  sm: "h-2 w-2",
  md: "h-2.5 w-2.5",
};

/** Four-state pulsing status indicator with accessible role=img wrapper. */
export function StatusDot({ state, pulse = false, size = "md", label }: StatusDotProps) {
  const bg = bgClass[state];
  const resolvedLabel = label ?? defaultLabel[state];
  const dotSize = sizeClass[size];

  return (
    <span
      role="img"
      aria-label={resolvedLabel}
      tabIndex={-1}
      className={`relative flex ${dotSize}`}
    >
      {pulse ? (
        <>
          {/* Outer ring: Tailwind animate-pulse opacity fade */}
          <span
            className={`absolute inset-0 rounded-full animate-pulse opacity-60 ${bg}`}
          />
          {/* Inner dot: pulse-glow keyframe via status-pulse CSS class */}
          <span className={`relative rounded-full status-pulse ${bg} ${dotSize}`} />
        </>
      ) : (
        <span className={`rounded-full ${bg} ${dotSize}`} />
      )}
    </span>
  );
}

export default StatusDot;
