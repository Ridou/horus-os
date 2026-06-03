"use client";

import { FileText, Clock } from "lucide-react";
import { useAgent } from "@/lib/hooks";
import { statusStyle } from "@/lib/status-colors";
import { timeAgo } from "@/lib/time";
import { PageSkeleton } from "@/components/PageSkeleton";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";

/** Full-page agent detail view. Consumes a resolved slug from the page server component. */
export function AgentDetailView({ slug }: { slug: string }) {
  const { data, isLoading, isError } = useAgent(slug);

  const agent = data?.agent;
  const style = agent ? statusStyle(agent.status) : null;

  if (isLoading) {
    return (
      <div>
        <PageSkeleton variant="detail" />
      </div>
    );
  }

  if (isError || !agent) {
    return (
      <div>
        <EmptyState icon={FileText} message="Could not load this agent." />
      </div>
    );
  }

  return (
    <div>
      {/* Page header with color dot inline with agent name */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold tracking-tight text-text-primary">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: agent.color }}
            />
            {agent.name}
          </h1>
          <p className="mt-1 text-sm text-text-secondary">{agent.description}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={agent.status} />
        </div>
      </div>

      <div className="space-y-6">
        {/* Meta */}
        <div className="space-y-2 text-xs">
          <dl className="grid grid-cols-2 gap-2">
            <div>
              <dt className="text-[10px] uppercase tracking-wider text-text-muted">
                Model
              </dt>
              <dd className="text-text-primary">{agent.default_model}</dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wider text-text-muted">
                Traces
              </dt>
              <dd className="text-text-primary tabular-nums">
                {agent.trace_count}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wider text-text-muted">
                Status
              </dt>
              <dd
                className="font-bold"
                style={{ color: style?.dot }}
              >
                {style?.label}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wider text-text-muted">
                Last active
              </dt>
              <dd className="text-text-primary">
                {timeAgo(agent.last_active_at)}
              </dd>
            </div>
          </dl>
        </div>

        {/* Soul markdown */}
        <div>
          <h3 className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-text-secondary">
            <FileText className="h-3 w-3" />
            Soul
          </h3>
          {data?.soul_markdown ? (
            <div className="border border-border-subtle bg-bg-primary p-3">
              <MarkdownRenderer content={data.soul_markdown} />
            </div>
          ) : (
            <p className="text-xs text-text-muted">
              No soul document for this agent.
            </p>
          )}
        </div>

        {/* Recent traces */}
        <div>
          <h3 className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-text-secondary">
            <Clock className="h-3 w-3" />
            Recent traces
          </h3>
          {data?.recent_traces && data.recent_traces.length > 0 ? (
            <ul className="space-y-1.5">
              {data.recent_traces.map((trace) => (
                <li
                  key={trace.trace_id}
                  className="border border-border-subtle bg-bg-primary p-2.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-[10px] text-text-muted">
                      {trace.trace_id}
                    </span>
                    <StatusBadge status={trace.status} />
                  </div>
                  <p className="mt-1 text-xs text-text-secondary">
                    {trace.prompt}
                  </p>
                  <span className="mt-1 block text-[10px] text-text-muted">
                    {timeAgo(trace.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-text-muted">No recent traces.</p>
          )}
        </div>
      </div>
    </div>
  );
}
