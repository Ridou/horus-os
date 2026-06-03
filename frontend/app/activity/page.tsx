"use client";

import { useMemo } from "react";
import { Activity as ActivityIcon } from "lucide-react";
import { useActivity, useTeam } from "@/lib/hooks";
import { cn } from "@/lib/cn";
import { timeAgo } from "@/lib/time";
import { useTabParam } from "@/lib/use-tab-param";
import type { ActivityEvent } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { PageSkeleton } from "@/components/PageSkeleton";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";

/** Fallback dot color when an event references an agent not on the team. */
const FALLBACK_COLOR = "#6b7280";

function TimelineRow({
  event,
  color,
  isLast,
}: {
  event: ActivityEvent;
  color: string;
  isLast: boolean;
}) {
  return (
    <li className="relative flex gap-4 pl-1">
      {/* Connector line */}
      {!isLast && (
        <span
          className="absolute left-[7px] top-5 h-full w-px bg-border-subtle"
          aria-hidden
        />
      )}
      {/* Dot */}
      <span
        className="relative z-10 mt-1.5 h-3.5 w-3.5 shrink-0 rounded-full ring-4 ring-bg-primary"
        style={{ backgroundColor: color }}
      />
      {/* Body */}
      <div className="min-w-0 flex-1 border border-border-subtle bg-bg-secondary p-3 transition-colors border-glow">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-text-primary">
                {event.agent}
              </span>
              <span className="rounded-full bg-bg-elevated px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-text-muted">
                {event.kind}
              </span>
            </div>
            <p className="mt-1 text-xs text-text-secondary">{event.summary}</p>
          </div>
          <StatusBadge status={event.status} />
        </div>
        <div className="mt-2 flex items-center gap-2 text-[10px] text-text-muted">
          <span className="font-mono">{event.trace_id}</span>
          <span>-</span>
          <span>{timeAgo(event.created_at)}</span>
        </div>
      </div>
    </li>
  );
}

export default function ActivityPage() {
  const { data, isLoading } = useActivity(50);
  const { data: team } = useTeam();
  const [agentFilter, setAgentFilter] = useTabParam<string>("agent", "all");

  const events = useMemo(() => data?.events ?? [], [data]);

  const colorByAgent = useMemo(() => {
    const map: Record<string, string> = {};
    for (const a of team?.agents ?? []) map[a.name] = a.color;
    return map;
  }, [team]);

  const agentNames = useMemo(() => {
    const names = new Set<string>();
    for (const e of events) names.add(e.agent);
    return Array.from(names).sort((a, b) => a.localeCompare(b));
  }, [events]);

  const filtered = useMemo(
    () =>
      agentFilter === "all"
        ? events
        : events.filter((e) => e.agent === agentFilter),
    [events, agentFilter],
  );

  return (
    <div>
      <PageHeader
        title="Activity"
        description="A timeline of what every agent has been doing, newest first."
        actions={
          agentNames.length > 0 ? (
            <label className="flex items-center gap-2 text-[11px] text-text-muted">
              Agent
              <select
                value={agentFilter}
                onChange={(e) => setAgentFilter(e.target.value)}
                aria-label="Filter by agent"
                className="border border-border-subtle bg-bg-secondary px-2 py-1.5 text-[11px] text-text-primary focus:border-accent-cyan focus:outline-none"
              >
                <option value="all">All agents</option>
                {agentNames.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          ) : undefined
        }
      />

      {isLoading ? (
        <PageSkeleton variant="list" />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={ActivityIcon}
          message={
            agentFilter === "all"
              ? "No activity yet. Events will appear here as your agents run."
              : `No activity for ${agentFilter}.`
          }
        />
      ) : (
        <ol data-tour-step="6" className={cn("space-y-3")}>
          {filtered.map((event, i) => (
            <TimelineRow
              key={event.trace_id}
              event={event}
              color={colorByAgent[event.agent] ?? FALLBACK_COLOR}
              isLast={i === filtered.length - 1}
            />
          ))}
        </ol>
      )}
    </div>
  );
}
