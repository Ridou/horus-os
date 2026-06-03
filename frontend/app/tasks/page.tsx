"use client";

import { useMemo, useState } from "react";
import { CheckSquare } from "lucide-react";
import { useTasks } from "@/lib/hooks";
import { api } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/cn";
import { timeAgo } from "@/lib/time";
import { useTabParam } from "@/lib/use-tab-param";
import type { Task } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { PageSkeleton } from "@/components/PageSkeleton";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { StatusIcon } from "@/components/StatusIcon";

type TaskStatusFilter = "all" | "pending" | "running" | "completed";

const TASK_FILTERS: { key: TaskStatusFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "pending", label: "Pending" },
  { key: "running", label: "Running" },
  { key: "completed", label: "Completed" },
];

function canRetry(status: Task["status"]): boolean {
  return status === "error" || status === "completed";
}

function canCancel(status: Task["status"]): boolean {
  return status === "pending" || status === "running";
}

export default function TasksPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useTasks();
  const allTasks = useMemo(() => data?.tasks ?? [], [data]);

  const [statusFilter, setStatusFilter] =
    useTabParam<TaskStatusFilter>("status", "all");
  const [confirmingCancel, setConfirmingCancel] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  const counts = useMemo(() => {
    const c: Record<TaskStatusFilter, number> = {
      all: allTasks.length,
      pending: 0,
      running: 0,
      completed: 0,
    };
    for (const t of allTasks) {
      if (t.status === "pending") c.pending += 1;
      if (t.status === "running") c.running += 1;
      if (t.status === "completed") c.completed += 1;
    }
    return c;
  }, [allTasks]);

  const filtered = useMemo(() => {
    if (statusFilter === "all") return allTasks;
    return allTasks.filter((t) => t.status === statusFilter);
  }, [allTasks, statusFilter]);

  async function handleCancel(taskId: string) {
    setCancelling(true);
    try {
      await api.deleteTask(taskId);
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks("") });
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks("pending") });
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks("running") });
      setConfirmingCancel(null);
    } catch {
      // deletion failed; keep confirm row open so user can retry
    } finally {
      setCancelling(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Tasks"
        description="Pending, running, and completed work items for your agents."
      />

      {/* Status filter tabs */}
      <div className="mb-4 flex flex-wrap items-center overflow-hidden border border-border-subtle">
        {TASK_FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setStatusFilter(f.key)}
            className={cn(
              "px-3 py-2 text-[11px] font-bold transition-colors",
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
      ) : isError ? (
        <EmptyState
          icon={CheckSquare}
          heading="Could not load tasks"
          message="Check your connection and refresh the page."
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={CheckSquare}
          heading="No tasks yet"
          message="Tasks will appear here when your agents receive work."
        />
      ) : (
        <ul className="space-y-2">
          {filtered.map((task) => (
            <li key={task.task_id} className="group">
              <div className="flex items-start gap-3 border border-border-subtle bg-bg-secondary px-4 py-3">
                {/* Left: status icon */}
                <div className="mt-0.5 shrink-0">
                  <StatusIcon status={task.status as Parameters<typeof StatusIcon>[0]["status"]} />
                </div>

                {/* Middle: title + agent + description */}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-bold text-text-primary">
                    {task.title}
                  </p>
                  {task.agent_profile_name && (
                    <p className="text-xs text-text-secondary">
                      {task.agent_profile_name}
                    </p>
                  )}
                  {task.description && (
                    <p className="line-clamp-1 text-xs text-text-muted">
                      {task.description}
                    </p>
                  )}
                </div>

                {/* Right: badge + time + actions */}
                <div className="flex shrink-0 flex-col items-end gap-1.5">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={task.status as Parameters<typeof StatusBadge>[0]["status"]} />
                    <span className="text-[10px] text-text-muted tabular-nums">
                      {timeAgo(task.updated_at)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {canRetry(task.status) && (
                      <button
                        type="button"
                        disabled
                        title="Retry is not yet available"
                        className="text-xs font-bold text-text-muted cursor-not-allowed"
                      >
                        Retry
                      </button>
                    )}
                    {canCancel(task.status) && (
                      <button
                        type="button"
                        className="text-xs font-bold text-danger hover:text-danger"
                        onClick={() => setConfirmingCancel(task.task_id)}
                      >
                        Cancel task
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Inline cancel confirmation */}
              {confirmingCancel === task.task_id ? (
                <div className="flex items-center gap-3 border border-danger/30 bg-danger/5 px-4 py-3 text-xs mt-1">
                  <span className="text-text-secondary">Cancel this task?</span>
                  <button
                    type="button"
                    className="font-bold text-danger hover:text-danger ml-auto"
                    disabled={cancelling}
                    onClick={() => handleCancel(task.task_id)}
                  >
                    Yes, cancel
                  </button>
                  <button
                    type="button"
                    className="text-text-secondary hover:text-text-primary"
                    onClick={() => setConfirmingCancel(null)}
                  >
                    Never mind
                  </button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
