"use client";

import Link from "next/link";
import { Users, Brain, Network, DollarSign, ArrowRight } from "lucide-react";
import { useHealth, useTeam } from "@/lib/hooks";
import { agentSlug } from "@/lib/api";
import { formatBytes } from "@/lib/time";
import { PageHeader } from "@/components/PageHeader";
import { MetricCard } from "@/components/MetricCard";
import { PageSkeleton } from "@/components/PageSkeleton";
import { StatusIcon } from "@/components/StatusIcon";

/** Rough cost estimate from trace volume, for the overview card. */
function estimateCost(traceCount: number): string {
  const usd = traceCount * 0.012;
  return `$${usd.toFixed(2)}`;
}

/**
 * The dashboard home: a live overview of the team and runtime. This is what a
 * local install opens into. In demo mode the marketing landing renders at "/"
 * instead, and this view is reached from "Launch the demo".
 */
export function DashboardHome() {
  const { data: health, isLoading: healthLoading } = useHealth();
  const { data: team, isLoading: teamLoading } = useTeam();

  const agents = team?.agents ?? [];

  return (
    <div>
      <PageHeader
        title="Welcome to horus-os"
        description="Your self-hosted autonomous AI command center. Here is the state of your team at a glance."
      />

      {healthLoading ? (
        <PageSkeleton variant="dashboard" />
      ) : (
        <>
          <div data-tour-step="1" className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <MetricCard
              title="Agents"
              value={health?.agent_count ?? agents.length}
              icon={Users}
            />
            <MetricCard
              title="Notes"
              value={health?.note_count ?? 0}
              icon={Brain}
            />
            <MetricCard
              title="Traces"
              value={health?.trace_count ?? 0}
              icon={Network}
            />
            <MetricCard
              title="Est. Cost"
              value={estimateCost(health?.trace_count ?? 0)}
              icon={DollarSign}
            />
          </div>

          <div className="mt-3 text-[11px] text-text-muted">
            {health
              ? `Database ${formatBytes(health.db_size_bytes)} - version ${health.version} - status ${health.status}`
              : null}
          </div>
        </>
      )}

      {/* Your team strip */}
      <section className="mt-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-wider text-text-secondary">
            Your team
          </h2>
          <Link
            href="/team"
            className="inline-flex items-center gap-1 text-xs text-accent-cyan hover:underline"
          >
            View all
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        {teamLoading ? (
          <PageSkeleton variant="list" />
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {agents.map((agent) => (
              <Link
                key={agent.name}
                href={`/team?agent=${agentSlug(agent.name)}`}
                className="group flex items-center gap-3 border border-border-subtle bg-bg-secondary p-3 transition-colors border-glow"
              >
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: agent.color }}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-bold text-text-primary">
                      {agent.name}
                    </span>
                    <StatusIcon status={agent.status} />
                  </div>
                  <p className="truncate text-xs text-text-muted">
                    {agent.description}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default DashboardHome;
