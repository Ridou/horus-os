"use client";

import Image from "next/image";
import Link from "next/link";
import { GitBranch, BookOpen, Check, X, ArrowUpRight, RotateCcw, ChevronRight } from "lucide-react";
import { useHealth } from "@/lib/hooks";
import { PageHeader } from "@/components/PageHeader";
import { useTour } from "@/components/TourProvider";

/** Public project links. */
const REPO_URL = "https://github.com/Ridou/horus-os";
const DOCS_URL = "https://github.com/Ridou/horus-os#readme";

/** The starter team, mirrored from the default agent roster. */
const TEAM = [
  {
    name: "Coordinator",
    color: "#00d4ff",
    role: "Routes goals, delegates to specialists, and tracks progress.",
  },
  {
    name: "Engineer",
    color: "#22c55e",
    role: "Writes, refactors, and reviews code, then runs the tests.",
  },
  {
    name: "Researcher",
    color: "#ec4899",
    role: "Gathers sources, summarizes findings, and verifies claims.",
  },
  {
    name: "Writer",
    color: "#f59e0b",
    role: "Drafts and edits prose, docs, and release notes in voice.",
  },
  {
    name: "Operator",
    color: "#a78bfa",
    role: "Handles deployments, schedules, and routine maintenance.",
  },
];

const IS = [
  "Open source and Apache 2.0 licensed.",
  "Self-hosted and local first. Your data stays on your machine.",
  "Built around a small team of cooperating agents.",
  "Provider agnostic, with first-class Anthropic and Gemini support.",
];

const IS_NOT = [
  "A hosted SaaS or an account you sign up for.",
  "A place that ships your data to a third party.",
  "A single monolithic model behind a chat box.",
  "Locked to one LLM vendor.",
];

export default function AboutPage() {
  const { data: health } = useHealth();
  const version = health?.version ?? "0.7.0";
  const { startTour } = useTour();

  return (
    <div>
      <PageHeader
        title="About"
        description="What horus-os is, who runs it, and where to go next."
      />

      {/* Hero */}
      <section className="flex flex-col items-start gap-5 border border-border-subtle bg-bg-secondary p-6 gradient-cyber sm:flex-row sm:items-center">
        <Image
          src="/horus-eye.svg"
          alt="horus-os"
          width={64}
          height={48}
          priority
          className="status-pulse shrink-0"
        />
        <div className="min-w-0">
          <h2 className="text-2xl font-bold tracking-tight text-text-primary">
            horus<span className="text-accent-cyan">-os</span>
          </h2>
          <p className="mt-1 text-sm font-medium text-accent-cyan">
            Your self-hosted autonomous AI command center.
          </p>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-text-secondary">
            horus-os runs a small team of cooperating agents on your own
            hardware. The runtime is Python with SQLite for persistence, and
            this dashboard is a static Next.js export bundled alongside it. It
            works fully offline in demo mode, which serves bundled sample data so
            the interface renders with no backend.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Link
              href={REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 border border-border-subtle bg-bg-elevated px-3 py-1.5 text-xs font-medium text-text-primary transition-colors hover:border-accent-cyan/40"
            >
              <GitBranch className="h-3.5 w-3.5" />
              GitHub
              <ArrowUpRight className="h-3 w-3 text-text-muted" />
            </Link>
            <Link
              href={DOCS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 border border-border-subtle bg-bg-elevated px-3 py-1.5 text-xs font-medium text-text-primary transition-colors hover:border-accent-cyan/40"
            >
              <BookOpen className="h-3.5 w-3.5" />
              Docs
              <ArrowUpRight className="h-3 w-3 text-text-muted" />
            </Link>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-cyan/10 px-3 py-1.5 text-[11px] font-medium text-accent-cyan">
              v{version}
            </span>
          </div>
        </div>
      </section>

      {/* Tour replay */}
      <section className="mt-6">
        <button
          type="button"
          data-tour-step="5"
          onClick={() => startTour()}
          className="border border-border-subtle bg-bg-secondary p-4 flex items-center gap-3 w-full text-left transition-colors hover:border-accent-cyan/40"
        >
          <RotateCcw className="h-4 w-4 text-accent-cyan shrink-0" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-bold text-text-primary">
              Replay the onboarding tour
            </p>
            <p className="text-xs text-text-secondary mt-0.5">
              Step through the core pages again to rediscover what horus-os can do.
            </p>
          </div>
          <ChevronRight className="h-4 w-4 text-text-muted shrink-0" />
        </button>
      </section>

      {/* Team showcase */}
      <section className="mt-8">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-text-secondary">
          The starter team
        </h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {TEAM.map((agent) => (
            <div
              key={agent.name}
              className="flex flex-col gap-2 border border-border-subtle bg-bg-secondary p-4 border-glow"
            >
              <div className="flex items-center gap-2.5">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: agent.color }}
                />
                <span className="text-sm font-semibold text-text-primary">
                  {agent.name}
                </span>
              </div>
              <p className="text-xs leading-relaxed text-text-secondary">
                {agent.role}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* What it is / is not */}
      <section className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="border border-border-subtle bg-bg-secondary p-4">
          <h3 className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-success">
            <Check className="h-3.5 w-3.5" />
            What horus-os is
          </h3>
          <ul className="space-y-2">
            {IS.map((item) => (
              <li
                key={item}
                className="flex items-start gap-2 text-xs leading-relaxed text-text-secondary"
              >
                <Check className="mt-0.5 h-3 w-3 shrink-0 text-success" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="border border-border-subtle bg-bg-secondary p-4">
          <h3 className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-danger">
            <X className="h-3.5 w-3.5" />
            What it is not
          </h3>
          <ul className="space-y-2">
            {IS_NOT.map((item) => (
              <li
                key={item}
                className="flex items-start gap-2 text-xs leading-relaxed text-text-secondary"
              >
                <X className="mt-0.5 h-3 w-3 shrink-0 text-danger" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}
