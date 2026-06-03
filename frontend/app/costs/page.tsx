"use client";

import { useMemo } from "react";
import {
  DollarSign,
  Gauge,
  Activity as ActivityIcon,
  Wrench,
  AlertTriangle,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from "recharts";
import {
  useCostByAgent,
  useCostByModel,
  useLatency,
  useTools,
  useTeam,
} from "@/lib/hooks";
import { cn } from "@/lib/cn";
import { timeAgo } from "@/lib/time";
import { useTabParam } from "@/lib/use-tab-param";
import type { CostByAgentRow, ToolReliabilityRow } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { PageSkeleton } from "@/components/PageSkeleton";
import { EmptyState } from "@/components/EmptyState";
import { MetricCard } from "@/components/MetricCard";

const WINDOWS: { key: string; label: string }[] = [
  { key: "24h", label: "24h" },
  { key: "7d", label: "7d" },
  { key: "30d", label: "30d" },
];

function formatUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  if (value >= 1) return `$${value.toFixed(2)}`;
  return `$${value.toFixed(4)}`;
}

function formatMs(ms: number | null): string {
  if (ms === null) return "-";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

/** Minimum sample size before a percentile is trustworthy (matches backend). */
const MIN_SAMPLES = 10;

function chartColor(index: number, fallbackColors: string[]): string {
  return fallbackColors[index % fallbackColors.length];
}

function ToolRow({ tool }: { tool: ToolReliabilityRow }) {
  const ratePct =
    tool.success_rate === null ? null : Math.round(tool.success_rate * 1000) / 10;
  const healthy = ratePct === null ? true : ratePct >= 95;
  return (
    <div className="border-b border-border-subtle px-4 py-3 last:border-b-0">
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-xs text-text-primary">
          {tool.tool_name}
        </span>
        <span
          className={cn(
            "text-xs font-bold tabular-nums",
            ratePct === null
              ? "text-text-muted"
              : healthy
                ? "text-success"
                : "text-warning",
          )}
        >
          {ratePct === null ? "n/a" : `${ratePct}%`}
        </span>
      </div>
      {/* Reliability bar */}
      <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-bg-elevated">
        <div
          className={cn(
            "h-full rounded-full",
            healthy ? "bg-success" : "bg-warning",
          )}
          style={{ width: `${ratePct ?? 0}%` }}
        />
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[10px] text-text-muted">
        <span className="tabular-nums">{tool.call_count} calls</span>
        {tool.error_count > 0 && (
          <span className="tabular-nums text-danger">
            {tool.error_count} errors
          </span>
        )}
        {tool.retry_then_success_count > 0 && (
          <span className="tabular-nums text-warning">
            {tool.retry_then_success_count} retried
          </span>
        )}
        {tool.last_error_type && (
          <span className="inline-flex items-center gap-1">
            <AlertTriangle className="h-2.5 w-2.5 text-danger" />
            <span className="font-mono">{tool.last_error_type}</span>
            {tool.last_error_at && <span>- {timeAgo(tool.last_error_at)}</span>}
          </span>
        )}
      </div>
    </div>
  );
}

export default function CostsPage() {
  const [since, setSince] = useTabParam<string>("since", "7d");

  const { data: costData, isLoading: costLoading } = useCostByAgent(since);
  const { data: modelData } = useCostByModel(since);
  const { data: latencyData } = useLatency(since);
  const { data: toolData } = useTools(since);
  const { data: team } = useTeam();

  const agents = useMemo(() => costData?.agents ?? [], [costData]);
  const models = useMemo(() => modelData?.models ?? [], [modelData]);
  const tools = useMemo(() => toolData?.tools ?? [], [toolData]);

  const colorByAgent = useMemo(() => {
    const map: Record<string, string> = {};
    for (const a of team?.agents ?? []) map[a.name] = a.color;
    return map;
  }, [team]);

  // Chart series identity colors: #00d4ff=accent-cyan, #22c55e=success,
  // #f59e0b=warning. #ec4899 and #a78bfa are non-token agent-identity colors
  // used for series differentiation and are acceptable as chart data values.
  const fallbackColors = ["#00d4ff", "#22c55e", "#ec4899", "#f59e0b", "#a78bfa"];

  // Summary metrics.
  const totalCost = useMemo(
    () => agents.reduce((sum, a) => sum + (a.total_cost_usd ?? 0), 0),
    [agents],
  );
  const totalRuns = useMemo(
    () => agents.reduce((sum, a) => sum + a.run_count, 0),
    [agents],
  );
  const uncostedRuns = useMemo(
    () => agents.reduce((sum, a) => sum + a.uncosted_runs, 0),
    [agents],
  );

  // Cost-by-agent bar chart data, sorted by cost descending.
  const chartData = useMemo(
    () =>
      [...agents]
        .sort((a, b) => (b.total_cost_usd ?? 0) - (a.total_cost_usd ?? 0))
        .map((a: CostByAgentRow) => ({
          agent: a.agent,
          cost: a.total_cost_usd ?? 0,
        })),
    [agents],
  );

  const latencyTrusted =
    latencyData !== undefined && latencyData.sample_count >= MIN_SAMPLES;

  return (
    <div>
      <PageHeader
        title="Costs"
        description="Spend, latency, and tool reliability across your providers."
        actions={
          <div className="flex items-center overflow-hidden border border-border-subtle">
            {WINDOWS.map((w) => (
              <button
                key={w.key}
                type="button"
                onClick={() => setSince(w.key)}
                className={cn(
                  "px-3 py-1.5 text-[11px] font-bold transition-colors",
                  since === w.key
                    ? "bg-bg-elevated text-text-primary"
                    : "text-text-muted hover:text-text-primary",
                )}
              >
                {w.label}
              </button>
            ))}
          </div>
        }
      />

      {costLoading ? (
        <PageSkeleton variant="dashboard" />
      ) : (
        <div className="space-y-6">
          {/* Summary metrics */}
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <MetricCard
              title="Total spend"
              value={formatUsd(totalCost)}
              icon={DollarSign}
              data={chartData.map((d) => d.cost)}
            />
            <MetricCard
              title="Total runs"
              value={totalRuns.toLocaleString()}
              icon={ActivityIcon}
            />
            <MetricCard
              title="Latency p50"
              value={latencyTrusted ? formatMs(latencyData.p50_ms) : "-"}
              icon={Gauge}
            />
            <MetricCard
              title="Latency p95"
              value={latencyTrusted ? formatMs(latencyData.p95_ms) : "-"}
              icon={Gauge}
            />
          </div>

          {uncostedRuns > 0 && (
            <p className="text-[11px] text-text-muted">
              {uncostedRuns.toLocaleString()} run
              {uncostedRuns === 1 ? "" : "s"} have no cost attached (unknown
              model pricing). They count toward runs but not spend.
            </p>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            {/* Cost by agent */}
            <section className="border border-border-subtle bg-bg-secondary p-4">
              <h2 className="mb-3 flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-text-secondary">
                <DollarSign className="h-3.5 w-3.5 text-text-muted" />
                Cost by agent
              </h2>
              {chartData.length === 0 ? (
                <EmptyState icon={DollarSign} message="No spend in this window." />
              ) : (
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={chartData}
                      layout="vertical"
                      margin={{ top: 0, right: 16, bottom: 0, left: 8 }}
                    >
                      <XAxis
                        type="number"
                        tick={{ fill: "var(--text-muted)", fontSize: 10 }}
                        tickFormatter={(v) => `$${Number(v).toFixed(2)}`}
                        axisLine={{ stroke: "var(--border-subtle)" }}
                        tickLine={false}
                      />
                      <YAxis
                        type="category"
                        dataKey="agent"
                        width={84}
                        tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        cursor={{ fill: "rgba(0,212,255,0.06)" }}
                        contentStyle={{
                          background: "#12131a",
                          border: "1px solid #2a2b35",
                          borderRadius: 6,
                          fontSize: 12,
                        }}
                        labelStyle={{ color: "#e0e0e0" }}
                        formatter={(value) => [
                          formatUsd(Number(value)),
                          "cost",
                        ]}
                      />
                      <Bar dataKey="cost" radius={[0, 3, 3, 0]}>
                        {chartData.map((d, i) => (
                          <Cell
                            key={d.agent}
                            fill={
                              colorByAgent[d.agent] ??
                              chartColor(i, fallbackColors)
                            }
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </section>

            {/* Cost by model */}
            <section className="border border-border-subtle bg-bg-secondary p-4">
              <h2 className="mb-3 flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-text-secondary">
                <DollarSign className="h-3.5 w-3.5 text-text-muted" />
                Cost by model
              </h2>
              {models.length === 0 ? (
                <EmptyState icon={DollarSign} message="No model spend yet." />
              ) : (
                <ul className="space-y-2">
                  {models.map((m) => (
                    <li
                      key={`${m.provider}-${m.model}`}
                      className="flex items-center justify-between gap-3 border border-border-subtle bg-bg-primary px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-mono text-xs text-text-primary">
                          {m.model}
                        </p>
                        <p className="text-[10px] capitalize text-text-muted">
                          {m.provider} - {m.call_count.toLocaleString()} calls
                        </p>
                      </div>
                      <span className="shrink-0 text-sm font-bold text-text-primary tabular-nums">
                        {formatUsd(m.total_cost_usd)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          {/* Latency detail */}
          <section className="border border-border-subtle bg-bg-secondary p-4">
            <h2 className="mb-3 flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-text-secondary">
              <Gauge className="h-3.5 w-3.5 text-text-muted" />
              Latency
            </h2>
            {!latencyTrusted ? (
              <p className="text-xs text-text-muted">
                Not enough samples in this window for a trustworthy percentile.
                {latencyData ? ` ${latencyData.sample_count} observed.` : ""}
              </p>
            ) : (
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-text-muted">
                    p50
                  </p>
                  <p className="mt-1 text-xl font-bold text-text-primary tabular-nums">
                    {formatMs(latencyData.p50_ms)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-text-muted">
                    p95
                  </p>
                  <p className="mt-1 text-xl font-bold text-text-primary tabular-nums">
                    {formatMs(latencyData.p95_ms)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-text-muted">
                    Samples
                  </p>
                  <p className="mt-1 text-xl font-bold text-text-primary tabular-nums">
                    {latencyData.sample_count.toLocaleString()}
                  </p>
                </div>
              </div>
            )}
          </section>

          {/* Tool reliability */}
          <section className="border border-border-subtle bg-bg-secondary">
            <h2 className="flex items-center gap-2 border-b border-border-subtle px-4 py-3 text-[11px] font-bold uppercase tracking-wider text-text-secondary">
              <Wrench className="h-3.5 w-3.5 text-text-muted" />
              Tool reliability
            </h2>
            {tools.length === 0 ? (
              <EmptyState icon={Wrench} message="No tool calls in this window." />
            ) : (
              <div>
                {tools.map((tool) => (
                  <ToolRow key={tool.tool_name} tool={tool} />
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
