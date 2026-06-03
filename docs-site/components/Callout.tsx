import type { ReactNode } from "react";
import { Info, AlertTriangle, Lightbulb, AlertOctagon, Flame } from "lucide-react";
import { cn } from "@/lib/cn";

export type CalloutType = "note" | "tip" | "important" | "warning" | "caution";

const STYLES: Record<
  CalloutType,
  { icon: typeof Info; label: string; color: string; bg: string; border: string }
> = {
  note: {
    icon: Info,
    label: "Note",
    color: "text-accent-cyan",
    bg: "bg-accent-cyan/5",
    border: "border-accent-cyan/30",
  },
  tip: {
    icon: Lightbulb,
    label: "Tip",
    color: "text-success",
    bg: "bg-success/5",
    border: "border-success/30",
  },
  important: {
    icon: Flame,
    label: "Important",
    color: "text-accent-cyan",
    bg: "bg-accent-cyan/5",
    border: "border-accent-cyan/30",
  },
  warning: {
    icon: AlertTriangle,
    label: "Warning",
    color: "text-warning",
    bg: "bg-warning/5",
    border: "border-warning/30",
  },
  caution: {
    icon: AlertOctagon,
    label: "Caution",
    color: "text-danger",
    bg: "bg-danger/5",
    border: "border-danger/30",
  },
};

/** GitHub-style admonition. Rendered from blockquotes beginning with [!TYPE]. */
export function Callout({
  type,
  title,
  children,
}: {
  type: CalloutType;
  title?: string;
  children: ReactNode;
}) {
  const s = STYLES[type];
  const Icon = s.icon;
  return (
    <div className={cn("my-5 rounded-md border px-4 py-3", s.bg, s.border)}>
      <div className={cn("mb-1 flex items-center gap-2 text-xs font-bold uppercase tracking-wider", s.color)}>
        <Icon className="h-4 w-4" />
        {title || s.label}
      </div>
      <div className="callout-body text-sm leading-relaxed text-text-secondary [&>:last-child]:mb-0">
        {children}
      </div>
    </div>
  );
}
