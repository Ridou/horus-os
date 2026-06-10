"use client";

import { useMemo, useState } from "react";
import {
  Network,
  ChevronRight,
  ChevronDown,
  Wrench,
  CornerDownRight,
  AlertTriangle,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useTraces, useTraceChildren } from "@/lib/hooks";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { timeAgo } from "@/lib/time";
import { useTabParam } from "@/lib/use-tab-param";
import type { Trace } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { PageSkeleton } from "@/components/PageSkeleton";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { ExampleDataBanner } from "@/components";

function formatLatency(ms: number | null): string {
  if (ms === null) return "-";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Provider-tinted chip so anthropic and gemini rows read apart at a glance. */
function ProviderChip({ provider, model }: { provider: string; model: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-bg-elevated px-2 py-0.5 text-[10px] font-medium text-text-secondary">
      <span className="capitalize">{provider}</span>
      <span className="text-text-muted">/</span>
      <span className="font-mono text-text-muted">{model}</span>
    </span>
  );
}

function TraceBody({ trace }: { trace: Trace }) {
  const { data, isLoading } = useTraceChildren(trace.trace_id);
  const children = data?.children ?? [];

  return (
    <div className="space-y-4 border-t border-border-subtle bg-bg-primary p-4">
      {/* Prompt */}
      <div>
        <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
          Prompt
        </h4>
        <p className="whitespace-pre-wrap text-xs leading-relaxed text-text-secondary">
          {trace.prompt}
        </p>
      </div>

      {/* Response */}
      <div>
        <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
          Response
        </h4>
        <p className="whitespace-pre-wrap text-xs leading-relaxed text-text-secondary">
          {trace.response_text || "(no response text)"}
        </p>
      </div>

      {/* Error */}
      {trace.error_message && (
        <div className="flex items-start gap-2 border border-danger/30 bg-danger/5 p-2.5">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" />
          <p className="font-mono text-[11px] leading-relaxed text-danger">
            {trace.error_message}
          </p>
        </div>
      )}

      {/* Tool uses */}
      {trace.tool_uses.length > 0 && (
        <div>
          <h4 className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
            <Wrench className="h-3 w-3" />
            Tool calls
          </h4>
          <ul className="space-y-1.5">
            {trace.tool_uses.map((tool) => (
              <li
                key={tool.id}
                className="flex flex-wrap items-center gap-2 border border-border-subtle bg-bg-secondary px-2.5 py-1.5"
              >
                <span className="font-mono text-[11px] text-accent-cyan">
                  {tool.name}
                </span>
                <span className="truncate font-mono text-[10px] text-text-muted">
                  {JSON.stringify(tool.input)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Usage */}
      {Object.keys(trace.usage).length > 0 && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-text-muted">
          {Object.entries(trace.usage).map(([key, value]) => (
            <span key={key} className="tabular-nums">
              {key.replace(/_/g, " ")}:{" "}
              <span className="text-text-secondary">
                {value.toLocaleString()}
              </span>
            </span>
          ))}
        </div>
      )}

      {/* Child traces */}
      <div>
        <h4 className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
          <CornerDownRight className="h-3 w-3" />
          Child traces
        </h4>
        {isLoading ? (
          <p className="text-[11px] text-text-muted">Loading children...</p>
        ) : children.length === 0 ? (
          <p className="text-[11px] text-text-muted">No child traces.</p>
        ) : (
          <ul className="space-y-1.5">
            {children.map((child) => (
              <li
                key={child.trace_id}
                className="border-l-2 border-border-subtle bg-bg-secondary p-2.5 pl-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="font-mono text-[10px] text-text-muted">
                      {child.trace_id}
                    </span>
                    {child.agent_profile_name && (
                      <span className="text-[11px] text-text-secondary">
                        {child.agent_profile_name}
                      </span>
                    )}
                  </div>
                  <StatusBadge status={child.status} />
                </div>
                <p className="mt-1 line-clamp-2 text-[11px] text-text-secondary">
                  {child.prompt}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function TraceRow({
  trace,
  expanded,
  onToggle,
}: {
  trace: Trace;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="border border-border-subtle bg-bg-secondary">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-bg-elevated/50"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-text-muted" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-text-muted" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <ProviderChip provider={trace.provider} model={trace.model} />
            {trace.agent_profile_name && (
              <span className="text-xs font-medium text-text-primary">
                {trace.agent_profile_name}
              </span>
            )}
          </div>
          <p className="mt-1 truncate text-xs text-text-secondary">
            {trace.prompt}
          </p>
        </div>
        <div className="hidden shrink-0 items-center gap-4 text-[10px] text-text-muted sm:flex">
          <span className="tabular-nums">{formatLatency(trace.latency_ms)}</span>
          <span className="tabular-nums">{timeAgo(trace.created_at)}</span>
        </div>
        <StatusBadge status={trace.status} />
      </button>
      {expanded && <TraceBody trace={trace} />}
    </div>
  );
}

export default function TracesPage() {
  const { data, isLoading, isError } = useTraces(50, 0);
  const traces = useMemo(() => data?.traces ?? [], [data]);
  const [expandedId, setExpandedId] = useTabParam<string>("trace", "");
  const queryClient = useQueryClient();

  // Only top-level traces (no parent) belong in the explorer list.
  const rootTraces = useMemo(
    () => traces.filter((t) => !t.parent_trace_id),
    [traces],
  );

  const demoTrace = useMemo(
    () => rootTraces.find((t) => t.provider === "example") ?? null,
    [rootTraces],
  );
  const hasDemoTrace = demoTrace !== null;

  const toggle = (id: string) =>
    setExpandedId(id === expandedId ? "" : id);

  return (
    <div>
      <PageHeader
        title="Traces"
        description="Every agent run, newest first. Expand a row to see the prompt, response, tool calls, and child traces."
      />

      {isLoading ? (
        <PageSkeleton variant="list" />
      ) : isError ? (
        <EmptyState
          icon={Network}
          message="Could not load traces. Check your connection and refresh the page."
        />
      ) : rootTraces.length === 0 ? (
        <EmptyState
          icon={Network}
          message="No traces yet. Runs will show up here as your agents work."
        />
      ) : (
        <div data-tour-step="7" className="space-y-2">
          {hasDemoTrace && (
            <ExampleDataBanner
              showClear
              onClear={async () => {
                await api.deleteTrace(demoTrace!.trace_id);
                queryClient.invalidateQueries({ predicate: () => true });
              }}
            />
          )}
          {rootTraces.map((trace) => (
            <TraceRow
              key={trace.trace_id}
              trace={trace}
              expanded={expandedId === trace.trace_id}
              onToggle={() => toggle(trace.trace_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
