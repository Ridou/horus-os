"use client";

import type { LucideIcon } from "lucide-react";
import { PageHeader } from "./PageHeader";
import { EmptyState } from "./EmptyState";

interface StubPageProps {
  title: string;
  description: string;
  icon: LucideIcon;
  message?: string;
}

/** Placeholder page for routes that ship later in this milestone. */
export function StubPage({ title, description, icon, message }: StubPageProps) {
  return (
    <div>
      <PageHeader title={title} description={description} />
      <EmptyState
        icon={icon}
        message={message ?? "Coming in this milestone."}
      />
    </div>
  );
}

export default StubPage;
