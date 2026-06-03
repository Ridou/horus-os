"use client";

import { useMemo } from "react";
import { List, GitBranch, Users } from "lucide-react";
import { useTeam } from "@/lib/hooks";
import { agentSlug } from "@/lib/api";
import { cn } from "@/lib/cn";
import { statusOrder } from "@/lib/status-colors";
import { timeAgo } from "@/lib/time";
import { useTabParam } from "@/lib/use-tab-param";
import type { Agent } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { PageSkeleton } from "@/components/PageSkeleton";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { StatusIcon } from "@/components/StatusIcon";
import { AgentDetailPanel } from "./AgentDetailPanel";
import { OrgView } from "./OrgView";

type ViewMode = "list" | "org";
type StatusFilter = "all" | "active" | "running" | "paused" | "idle" | "error";

const STATUS_FILTERS: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "active", label: "Active" },
  { key: "running", label: "Running" },
  { key: "paused", label: "Paused" },
  { key: "idle", label: "Idle" },
  { key: "error", label: "Error" },
];

function AgentCard({
  agent,
  selected,
  onSelect,
}: {
  agent: Agent;
  selected: boolean;
  onSelect: (slug: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(agentSlug(agent.name))}
      className={cn(
        "flex flex-col gap-2 border bg-bg-secondary p-4 text-left transition-colors border-glow",
        selected ? "border-accent-cyan" : "border-border-subtle",
      )}
    >
      <div className="flex items-center gap-2.5">
        <span
          className="h-2.5 w-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: agent.color }}
        />
        <span className="flex-1 truncate text-sm font-bold text-text-primary">
          {agent.name}
        </span>
        <StatusIcon status={agent.status} />
      </div>
      <p className="line-clamp-2 text-xs text-text-secondary">
        {agent.description}
      </p>
      <div className="mt-1 flex items-center justify-between">
        <StatusBadge status={agent.status} />
        <span className="text-[10px] text-text-muted tabular-nums">
          {agent.trace_count} traces - {timeAgo(agent.last_active_at)}
        </span>
      </div>
    </button>
  );
}

export default function TeamPage() {
  const { data, isLoading } = useTeam();
  const agents = useMemo(() => data?.agents ?? [], [data]);

  const [viewMode, setViewMode] = useTabParam<ViewMode>("view", "list");
  const [statusFilter, setStatusFilter] = useTabParam<StatusFilter>(
    "status",
    "all",
  );
  const [selectedAgent, setSelectedAgent] = useTabParam<string>("agent", "");

  const counts = useMemo(() => {
    const c: Record<StatusFilter, number> = {
      all: agents.length,
      active: 0,
      running: 0,
      paused: 0,
      idle: 0,
      error: 0,
    };
    for (const a of agents) {
      if (a.status === "active") c.active += 1;
      if (a.status === "running") c.running += 1;
      if (a.status === "paused") c.paused += 1;
      if (a.status === "idle") c.idle += 1;
      if (a.status === "error") c.error += 1;
    }
    return c;
  }, [agents]);

  const filtered = useMemo(() => {
    let list = [...agents];
    if (statusFilter !== "all") {
      list = list.filter((a) => a.status === statusFilter);
    }
    list.sort(
      (a, b) =>
        statusOrder(a.status) - statusOrder(b.status) ||
        a.name.localeCompare(b.name),
    );
    return list;
  }, [agents, statusFilter]);

  const selectedSlug = selectedAgent || null;

  const select = (slug: string) =>
    setSelectedAgent(slug === selectedSlug ? "" : slug);

  return (
    <div className="flex h-full">
      <div className="min-w-0 flex-1">
        <PageHeader
          title="Team"
          description="The agents that make up your command center. Select one to inspect its soul and recent traces."
          actions={
            <div className="flex items-center overflow-hidden border border-border-subtle">
              <button
                type="button"
                onClick={() => setViewMode("list")}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium transition-colors",
                  viewMode === "list"
                    ? "bg-bg-elevated text-text-primary"
                    : "text-text-muted hover:text-text-primary",
                )}
              >
                <List className="h-3.5 w-3.5" />
                List
              </button>
              <button
                type="button"
                onClick={() => setViewMode("org")}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium transition-colors",
                  viewMode === "org"
                    ? "bg-bg-elevated text-text-primary"
                    : "text-text-muted hover:text-text-primary",
                )}
              >
                <GitBranch className="h-3.5 w-3.5" />
                Org
              </button>
            </div>
          }
        />

        {/* Status filter tabs */}
        <div className="mb-4 flex flex-wrap items-center overflow-hidden border border-border-subtle">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setStatusFilter(f.key)}
              className={cn(
                "px-3 py-1.5 text-[11px] font-medium transition-colors",
                statusFilter === f.key
                  ? "bg-bg-elevated text-text-primary"
                  : "text-text-muted hover:bg-bg-elevated/60 hover:text-text-primary",
              )}
            >
              {f.label}
              <span className="ml-1.5 text-[10px] tabular-nums opacity-70">
                {counts[f.key]}
              </span>
            </button>
          ))}
        </div>

        {/* Content */}
        {isLoading ? (
          <PageSkeleton variant="list" />
        ) : viewMode === "org" ? (
          <div className="border border-border-subtle">
            <OrgView
              agents={agents}
              selectedSlug={selectedSlug}
              onSelect={select}
            />
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState icon={Users} message="No agents match this filter." />
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3" data-tour-step="2">
            {filtered.map((agent) => (
              <AgentCard
                key={agent.name}
                agent={agent}
                selected={selectedSlug === agentSlug(agent.name)}
                onSelect={select}
              />
            ))}
          </div>
        )}
      </div>

      {/* Detail panel */}
      {selectedSlug && (
        <div className="ml-4 hidden shrink-0 lg:block">
          <AgentDetailPanel
            slug={selectedSlug}
            onClose={() => setSelectedAgent("")}
          />
        </div>
      )}

      {/* Mobile detail overlay */}
      {selectedSlug && (
        <div className="fixed inset-0 z-40 flex bg-black/50 lg:hidden">
          <div className="ml-auto h-full w-full max-w-sm">
            <AgentDetailPanel
              slug={selectedSlug}
              onClose={() => setSelectedAgent("")}
            />
          </div>
        </div>
      )}
    </div>
  );
}
