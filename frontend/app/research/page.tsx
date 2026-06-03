"use client";

import { useState } from "react";
import Link from "next/link";
import { Telescope, Loader2, Network } from "lucide-react";
import { api } from "@/lib/api";
import { useResearchProgress, useResearchReport } from "@/lib/hooks";
import { cn } from "@/lib/cn";
import type {
  ResearchPhase,
  ResearchPlan,
  ResearchStartResponse,
} from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";

/** Human label for each phase the live progress panel can report. */
const PHASE_LABELS: Record<ResearchPhase, string> = {
  plan: "Planning",
  searching: "Searching",
  reading: "Reading",
  synthesizing: "Synthesizing",
  done: "Done",
  cancelled: "Cancelled",
  error: "Error",
};

/** Order of the active phases, used to fill the phase progress track. */
const ACTIVE_PHASES: ResearchPhase[] = [
  "plan",
  "searching",
  "reading",
  "synthesizing",
];

type Stage = "idle" | "plan" | "running";

export default function ResearchPage() {
  const [stage, setStage] = useState<Stage>("idle");
  const [question, setQuestion] = useState("");
  const [plan, setPlan] = useState<ResearchPlan | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Live progress drives the running panel and tells us when synthesis is done.
  const { data: progress } = useResearchProgress(
    stage === "running" ? taskId : null,
  );
  const phase = progress?.phase ?? "plan";
  const isDone = phase === "done";
  const isCancelled = phase === "cancelled";

  // The report is only fetched once the run reports a completed phase.
  const { data: report } = useResearchReport(taskId, isDone);

  async function handleSubmit() {
    const q = question.trim();
    if (!q) return;
    setSubmitting(true);
    setError(null);
    try {
      const res: ResearchStartResponse = await api.startResearch(q);
      setPlan(res.plan);
      setTaskId(res.task_id);
      setTraceId(res.trace_id);
      setStage("plan");
    } catch {
      setError(
        "Could not plan this research run. A local backend is required to start a real run.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStart() {
    if (!taskId) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.startResearchRun(taskId);
      setStage("running");
    } catch {
      setError("Could not start the run.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancel() {
    if (!taskId) return;
    try {
      await api.cancelResearch(taskId);
    } catch {
      // Cancel is best-effort; the progress panel reflects the real state.
    }
    if (stage === "plan") {
      reset();
    }
  }

  function reset() {
    setStage("idle");
    setQuestion("");
    setPlan(null);
    setTaskId(null);
    setTraceId(null);
    setError(null);
  }

  return (
    <div data-tour-step="5">
      <PageHeader
        title="Research"
        description="Run a deep, multi-source research pass and get a cited report. Review the plan before any work starts."
      />

      {error && (
        <p className="mb-4 border border-danger/30 bg-danger/5 px-4 py-3 text-xs text-danger">
          {error}
        </p>
      )}

      {/* Stage 1: question entry */}
      {stage === "idle" && (
        <div className="space-y-3">
          <label
            htmlFor="research-question"
            className="block text-xs font-bold text-text-secondary"
          >
            What do you want researched?
          </label>
          <textarea
            id="research-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={4}
            placeholder="e.g. What are the tradeoffs of running local LLMs for autonomous agents?"
            className="w-full resize-y border border-border-subtle bg-bg-secondary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-cyan focus:outline-none"
          />
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || !question.trim()}
            className="inline-flex items-center gap-2 bg-accent-cyan px-4 py-2 text-sm font-bold text-bg-primary transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Telescope className="h-4 w-4" />
            )}
            Plan research
          </button>
        </div>
      )}

      {/* Stage 2: plan preview, cancelable BEFORE execution (RESEARCH-02) */}
      {stage === "plan" && plan && (
        <div className="space-y-4">
          <div className="border border-border-subtle bg-bg-secondary px-4 py-3">
            <p className="text-sm font-bold text-text-primary">{plan.question}</p>
            <p className="mt-0.5 text-xs text-text-muted">
              Review the plan below. No searches or model calls run until you
              start the research.
            </p>
          </div>
          <ol className="space-y-2">
            {plan.subtopics.map((sub, i) => (
              <li
                key={i}
                className="flex items-start gap-3 border border-border-subtle bg-bg-secondary px-4 py-3"
              >
                <span className="mt-0.5 shrink-0 text-xs font-bold tabular-nums text-accent-cyan">
                  {i + 1}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-bold text-text-primary">
                    {sub.title || sub.query}
                  </p>
                  <p className="text-xs text-text-muted">{sub.query}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleStart}
              disabled={submitting}
              className="inline-flex items-center gap-2 bg-accent-cyan px-4 py-2 text-sm font-bold text-bg-primary transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              Start research
            </button>
            <button
              type="button"
              onClick={handleCancel}
              className="text-sm font-bold text-danger hover:text-danger"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Stage 3 + 4: live progress, then the cited report */}
      {stage === "running" && (
        <div className="space-y-4">
          {/* Live progress panel (RESEARCH-02 live progress) */}
          <div className="border border-border-subtle bg-bg-secondary px-4 py-4">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                {!isDone && !isCancelled && (
                  <Loader2 className="h-4 w-4 animate-spin text-accent-cyan" />
                )}
                <span className="text-sm font-bold text-text-primary">
                  {PHASE_LABELS[phase]}
                </span>
                <StatusBadge
                  status={
                    isDone ? "done" : isCancelled ? "cancelled" : "running"
                  }
                />
              </div>
              {!isDone && !isCancelled && (
                <button
                  type="button"
                  onClick={handleCancel}
                  className="text-xs font-bold text-danger hover:text-danger"
                >
                  Cancel run
                </button>
              )}
            </div>

            {/* Phase track */}
            <div className="mb-4 flex gap-1.5">
              {ACTIVE_PHASES.map((p) => {
                const reached =
                  isDone ||
                  ACTIVE_PHASES.indexOf(p) <= ACTIVE_PHASES.indexOf(phase);
                return (
                  <div
                    key={p}
                    title={PHASE_LABELS[p]}
                    className={cn(
                      "h-1.5 flex-1 rounded-full",
                      reached && !isCancelled
                        ? "bg-accent-cyan"
                        : "bg-bg-elevated",
                    )}
                  />
                );
              })}
            </div>

            <dl className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <dt className="text-text-muted">Sources found</dt>
                <dd className="text-sm font-bold tabular-nums text-text-primary">
                  {progress?.sources_found ?? 0}
                </dd>
              </div>
              <div>
                <dt className="text-text-muted">Iterations</dt>
                <dd className="text-sm font-bold tabular-nums text-text-primary">
                  {progress?.iterations_used ?? 0}
                  <span className="text-text-muted">
                    {" / "}
                    {progress?.iteration_budget ?? 0}
                  </span>
                </dd>
              </div>
            </dl>

            {/* Inspectable trace + tasks (RESEARCH-05) */}
            <div className="mt-4 flex items-center gap-4 border-t border-border-subtle pt-3 text-xs">
              {traceId && (
                <Link
                  href={`/traces?trace=${encodeURIComponent(traceId)}`}
                  className="inline-flex items-center gap-1.5 font-bold text-accent-cyan hover:underline"
                >
                  <Network className="h-3.5 w-3.5" />
                  View trace
                </Link>
              )}
              <Link
                href="/tasks"
                className="font-bold text-text-secondary hover:text-text-primary"
              >
                View in tasks
              </Link>
            </div>
          </div>

          {/* Cancelled state */}
          {isCancelled && (
            <EmptyState
              icon={Telescope}
              heading="Research cancelled"
              message="This run was cancelled. Start a new research pass when you are ready."
              action="New research"
              onAction={reset}
            />
          )}

          {/* Stage 4: the finished cited report (RESEARCH-03 / RESEARCH-05) */}
          {isDone && report && (
            <div className="border border-border-subtle bg-bg-secondary px-4 py-4">
              <MarkdownRenderer content={report.report} />
              <div className="mt-4 flex items-center gap-4 border-t border-border-subtle pt-3 text-xs">
                <button
                  type="button"
                  onClick={reset}
                  className="font-bold text-accent-cyan hover:underline"
                >
                  New research
                </button>
                {report.trace_id && (
                  <Link
                    href={`/traces?trace=${encodeURIComponent(report.trace_id)}`}
                    className="inline-flex items-center gap-1.5 font-bold text-text-secondary hover:text-text-primary"
                  >
                    <Network className="h-3.5 w-3.5" />
                    View trace
                  </Link>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
