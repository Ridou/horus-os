"use client";

import { Plus } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  message: string;
  heading?: string;
  action?: string;
  onAction?: () => void;
}

/** Centered icon + message + optional heading and action. */
export function EmptyState({ icon: Icon, message, heading, action, onAction }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 rounded-lg bg-bg-elevated p-4">
        <Icon className="h-10 w-10 text-text-muted" />
      </div>
      {heading && (
        <p className="mb-1 text-base font-bold text-text-primary">{heading}</p>
      )}
      <p className="mb-3 text-sm text-text-secondary">{message}</p>
      {action && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="inline-flex items-center gap-1.5 rounded-md border border-border-subtle px-3 py-1.5 text-xs font-bold text-text-secondary transition-colors hover:bg-bg-elevated hover:text-text-primary"
        >
          <Plus className="h-3.5 w-3.5" />
          {action}
        </button>
      )}
    </div>
  );
}

export default EmptyState;
