"use client";

import { useMemo } from "react";
import {
  Sparkles,
  Lightbulb,
  Trophy,
  AlertTriangle,
  HelpCircle,
  CheckCircle2,
  XCircle,
  Clock,
  type LucideIcon,
} from "lucide-react";
import { useReflections, useTeam } from "@/lib/hooks";
import { cn } from "@/lib/cn";
import { timeAgo } from "@/lib/time";
import { useTabParam } from "@/lib/use-tab-param";
import type {
  Reflection,
  ReflectionCategory,
  ReflectionView,
} from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { PageSkeleton } from "@/components/PageSkeleton";
import { EmptyState } from "@/components/EmptyState";

/** Dot color when a reflection references an agent not on the team. */
const FALLBACK_COLOR = "#6b7280";

const VIEW_TABS: { key: ReflectionView; label: string }[] = [
  { key: "feed", label: "Reflections" },
  { key: "growth", label: "Growth" },
  { key: "decisions", label: "Decisions" },
];

const CATEGORY_ICON: Record<ReflectionCategory, LucideIcon> = {
  improvement: Lightbulb,
  win: Trophy,
  risk: AlertTriangle,
  question: HelpCircle,
};

const EMPTY_COPY: Record<ReflectionView, string> = {
  feed: "No open reflections. When the daily routine runs, each agent's improvement ideas land here.",
  growth: "No wins yet. Shipped improvements and things agents did well will show here.",
  decisions:
    "No decisions yet. Accepted and dismissed items, with your reasons, will be recorded here.",
};

/** Importance pill styling, 5 (critical) down to 1 (note). */
function importanceMeta(n: number): { label: string; cls: string } {
  if (n >= 5)
    return { label: "Critical", cls: "border-danger/50 bg-danger/15 text-danger" };
  if (n === 4)
    return { label: "High", cls: "border-warning/50 bg-warning/15 text-warning" };
  if (n === 3)
    return {
      label: "Medium",
      cls: "border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan",
    };
  if (n === 2)
    return {
      label: "Low",
      cls: "border-border-subtle bg-bg-elevated text-text-secondary",
    };
  return {
    label: "Note",
    cls: "border-border-subtle bg-bg-elevated text-text-muted",
  };
}

function DispositionBadge({ status }: { status: Reflection["status"] }) {
  const map: Record<string, { label: string; cls: string; Icon: LucideIcon }> = {
    accepted: {
      label: "Accepted",
      cls: "border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan",
      Icon: CheckCircle2,
    },
    done: {
      label: "Done",
      cls: "border-success/40 bg-success/10 text-success",
      Icon: Trophy,
    },
    dismissed: {
      label: "Dismissed",
      cls: "border-border-subtle bg-bg-elevated text-text-muted",
      Icon: XCircle,
    },
  };
  const m = map[status] ?? map.dismissed;
  const Icon = m.Icon;
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
        m.cls,
      )}
    >
      <Icon className="h-3 w-3" />
      {m.label}
    </span>
  );
}

function ReflectionCard({
  r,
  color,
  view,
}: {
  r: Reflection;
  color: string;
  view: ReflectionView;
}) {
  const CatIcon = CATEGORY_ICON[r.category];
  const imp = importanceMeta(r.importance);
  const isWin = r.category === "win" || r.status === "done";

  return (
    <li
      className={cn(
        "border border-border-subtle bg-bg-secondary p-4 transition-colors border-glow",
        view === "growth" && isWin && "border-success/30",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span
            className="h-2.5 w-2.5 shrink-0 rounded-full"
            style={{ backgroundColor: color }}
            aria-hidden
          />
          <span className="text-sm font-semibold text-text-primary">
            {r.agent_profile_name}
          </span>
          <span className="inline-flex items-center gap-1 rounded-full bg-bg-elevated px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-text-muted">
            <CatIcon className="h-3 w-3" />
            {r.category}
          </span>
          {r.recurrence > 1 && (
            <span className="rounded-full border border-border-subtle px-2 py-0.5 text-[10px] text-text-muted">
              seen {r.recurrence}x
            </span>
          )}
        </div>
        {view === "feed" ? (
          <span
            className={cn(
              "shrink-0 rounded border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
              imp.cls,
            )}
          >
            {imp.label}
          </span>
        ) : view === "decisions" ? (
          <DispositionBadge status={r.status} />
        ) : (
          <Trophy className="h-4 w-4 shrink-0 text-success" aria-hidden />
        )}
      </div>

      <p className="mt-2 text-sm font-bold text-text-primary">{r.title}</p>
      <p className="mt-1 text-xs leading-relaxed text-text-secondary">{r.body}</p>

      {view === "decisions" && r.resolution && (
        <p className="mt-2 border-l-2 border-border-subtle pl-3 text-xs italic text-text-muted">
          {r.resolution}
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] text-text-muted">
        <Clock className="h-3 w-3" aria-hidden />
        <span>{timeAgo(r.created_at)}</span>
        <span>-</span>
        <span className="font-mono">{r.run_date}</span>
        <span>-</span>
        <span className="font-mono opacity-70">{r.item_key}</span>
        {view === "feed" && r.read_at === null && (
          <>
            <span>-</span>
            <span className="font-bold text-accent-cyan">unread</span>
          </>
        )}
      </div>

      {view === "feed" && (
        <div className="mt-3 flex items-center gap-4 border-t border-border-subtle pt-3">
          {["Accept", "Dismiss", "Mark done"].map((label) => (
            <button
              key={label}
              type="button"
              disabled
              title="Decisions light up once the reflection backend ships"
              className="cursor-not-allowed text-[11px] font-bold text-text-muted"
            >
              {label}
            </button>
          ))}
        </div>
      )}
    </li>
  );
}

export default function StandupPage() {
  const [view, setView] = useTabParam<ReflectionView>("view", "feed");
  const [agentFilter, setAgentFilter] = useTabParam<string>("agent", "all");
  const agentParam = agentFilter === "all" ? "" : agentFilter;

  const { data, isLoading, isError } = useReflections(view, agentParam);
  const { data: team } = useTeam();

  const items = useMemo(() => data?.reflections ?? [], [data]);

  const colorByAgent = useMemo(() => {
    const map: Record<string, string> = {};
    for (const a of team?.agents ?? []) map[a.name] = a.color;
    return map;
  }, [team]);

  const agentNames = useMemo(
    () => (team?.agents ?? []).map((a) => a.name).sort((x, y) => x.localeCompare(y)),
    [team],
  );

  const description =
    view === "growth"
      ? "Wins worth keeping, and improvements your agents have shipped."
      : view === "decisions"
        ? "What the team accepted or ruled out. Every agent reads this, so settled calls are not raised again."
        : "Each agent's daily take on how it can improve, most important first.";

  return (
    <div>
      <PageHeader
        title="Standup"
        description={description}
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

      {/* View tabs */}
      <div className="mb-4 flex flex-wrap items-center overflow-hidden border border-border-subtle">
        {VIEW_TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setView(t.key)}
            className={cn(
              "px-3 py-2 text-[11px] font-bold transition-colors",
              view === t.key
                ? "bg-bg-elevated text-text-primary"
                : "text-text-muted hover:bg-bg-elevated/60 hover:text-text-primary",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <p className="mb-4 text-[11px] text-text-muted">
        Preview with sample data. Reflections become live once the daily routine
        and the /api/reflections endpoint ship.
      </p>

      {isLoading ? (
        <PageSkeleton variant="list" />
      ) : isError ? (
        <EmptyState
          icon={Sparkles}
          heading="Could not load reflections"
          message="Check your connection and refresh the page."
        />
      ) : items.length === 0 ? (
        <EmptyState icon={Sparkles} message={EMPTY_COPY[view]} />
      ) : (
        <ul className="space-y-3">
          {items.map((r) => (
            <ReflectionCard
              key={r.reflection_id}
              r={r}
              color={colorByAgent[r.agent_profile_name] ?? FALLBACK_COLOR}
              view={view}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
