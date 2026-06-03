"use client";

import { X, FileText, Clock } from "lucide-react";
import { useAgent } from "@/lib/hooks";
import { statusStyle } from "@/lib/status-colors";
import { timeAgo } from "@/lib/time";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";

interface AgentDetailPanelProps {
  /** Selected agent slug, or null when nothing is selected. */
  slug: string | null;
  onClose: () => void;
}

function PanelSkeleton() {
  return (
    <div className="space-y-4">
      <div className="h-6 w-1/2 animate-pulse rounded bg-bg-elevated" />
      <div className="h-4 w-2/3 animate-pulse rounded bg-bg-elevated" />
      <div className="h-40 w-full animate-pulse rounded bg-bg-elevated" />
    </div>
  );
}

/** Client-side detail drawer for the selected agent. */
export function AgentDetailPanel({ slug, onClose }: AgentDetailPanelProps) {
  const { data, isLoading, isError } = useAgent(slug);

  if (!slug) return null;

  const agent = data?.agent;
  const style = agent ? statusStyle(agent.status) : null;

  return (
    <aside
      className="flex h-full w-full flex-col border-l border-border-subtle bg-bg-secondary lg:w-[420px]"
      aria-label="Agent detail"
    >
      <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          {agent && (
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: agent.color }}
            />
          )}
          <h2 className="truncate text-sm font-bold text-text-primary">
            {agent?.name ?? "Agent"}
          </h2>
          {agent && <StatusBadge status={agent.status} />}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close detail panel"
          className="rounded p-1 text-text-muted transition-colors hover:bg-bg-elevated hover:text-text-primary"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {isLoading ? (
          <PanelSkeleton />
        ) : isError || !agent ? (
          <EmptyState icon={FileText} message="Could not load this agent." />
        ) : (
          <div className="space-y-6">
            {/* Meta */}
            <div className="space-y-2 text-xs">
              <p className="text-text-secondary">{agent.description}</p>
              <dl className="grid grid-cols-2 gap-2 pt-2">
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
                    className="font-medium"
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
              <h3 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-secondary">
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
              <h3 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-secondary">
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
        )}
      </div>
    </aside>
  );
}

export default AgentDetailPanel;
