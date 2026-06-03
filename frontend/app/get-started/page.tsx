"use client";

import Link from "next/link";
import {
  Download,
  KeyRound,
  Play,
  ArrowUpRight,
  ArrowRight,
  Sparkles,
  Plug,
} from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { CopyButton, CommandBlock } from "@/components";

/** An external link styled like the about-page chips. */
function ExternalLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 border border-border-subtle bg-bg-elevated px-3 py-1.5 text-xs font-bold text-text-primary transition-colors hover:border-accent-cyan/40"
    >
      {label}
      <ArrowUpRight className="h-3 w-3 text-text-muted" />
    </Link>
  );
}

/** One numbered onboarding step in a card. */
function Step({
  number,
  icon: Icon,
  title,
  children,
}: {
  number: number;
  icon: typeof Download;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border border-border-subtle bg-bg-secondary p-5 border-glow">
      <div className="mb-4 flex items-center gap-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-cyan/10 text-sm font-bold text-accent-cyan tabular-nums">
          {number}
        </span>
        <h2 className="flex items-center gap-2 text-base font-bold text-text-primary">
          <Icon className="h-4 w-4 text-accent-cyan" />
          {title}
        </h2>
      </div>
      <div className="space-y-3 pl-10">{children}</div>
    </section>
  );
}

/**
 * Onboarding page. Renders in both demo and local modes from the sidebar nav
 * and the marketing landing CTAs. Three numbered steps with copy-pasteable
 * commands, then a short closing note back to the demo.
 */
export default function GetStartedPage() {
  return (
    <div>
      <PageHeader
        title="Get started"
        description="Install horus-os, add a provider key, and run your first agent. A few commands and you are live."
      />

      <div className="space-y-4">
        {/* Step 1: install */}
        <Step number={1} icon={Download} title="Install">
          <p className="text-sm leading-relaxed text-text-secondary">
            horus-os ships as a Python package. The{" "}
            <code className="text-accent-cyan">[all]</code> extra pulls in both
            provider SDKs and the bundled dashboard. Python 3.11 or newer is
            required.
          </p>
          <CommandBlock command="pip install 'horus-os[all]'" />
        </Step>

        {/* Step 2: add your API keys */}
        <Step number={2} icon={KeyRound} title="Add your API keys">
          <p className="text-sm leading-relaxed text-text-secondary">
            Run the interactive setup. It walks you through pasting your keys,
            validates each one live against the provider before saving, and
            writes them to a local config. horus-os needs at least one provider
            key, and your keys stay on your machine.
          </p>
          <CommandBlock command="horus-os init --interactive" />

          <p className="text-sm leading-relaxed text-text-secondary">
            Need a key? Create one from your provider console:
          </p>
          <div className="flex flex-wrap gap-2">
            <ExternalLink
              href="https://console.anthropic.com/"
              label="Anthropic Console"
            />
            <ExternalLink
              href="https://aistudio.google.com/apikey"
              label="Google AI Studio"
            />
          </div>

          <p className="text-sm leading-relaxed text-text-secondary">
            Prefer environment variables? Export at least one of these instead
            of running init:
          </p>
          <CommandBlock command="export ANTHROPIC_API_KEY=..." />
          <CommandBlock command="export GEMINI_API_KEY=..." />
        </Step>

        {/* Step 3: use it */}
        <Step number={3} icon={Play} title="Use it">
          <p className="text-sm leading-relaxed text-text-secondary">
            Hand your team a goal from the command line, or start the local
            server and drive everything from the dashboard.
          </p>
          <CommandBlock command={`horus-os run "Summarize today's notes."`} />
          <CommandBlock command="horus-os serve" />
          <p className="text-sm leading-relaxed text-text-secondary">
            <code className="text-accent-cyan">horus-os serve</code> opens the
            dashboard at{" "}
            <a
              href="http://127.0.0.1:8765"
              className="text-accent-cyan hover:underline"
            >
              http://127.0.0.1:8765
            </a>
            , the same interface you see in the demo, now running your own
            agents.
          </p>
        </Step>
        {/* Step 4: Connect your integrations */}
        <Step number={4} icon={Plug} title="Connect your integrations">
          <p className="text-sm leading-relaxed text-text-secondary">
            The Integrations page shows every available connector with live
            status indicators. Open a guided walkthrough for any integration to
            see what it unlocks, where to get credentials, and the exact env var
            to set.
          </p>
          <Link
            href="/integrations/"
            className="inline-flex items-center gap-2 border border-accent-cyan bg-accent-cyan px-4 py-2 text-sm font-bold text-bg-primary transition-shadow hover:glow-cyan"
          >
            View integrations
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Step>
      </div>

      {/* Closing note */}
      <section className="mt-6 flex flex-col items-start gap-4 border border-border-subtle bg-bg-secondary p-6 gradient-cyber sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-accent-cyan" />
          <div>
            <h2 className="text-base font-bold text-text-primary">
              You are all set
            </h2>
            <p className="mt-1 max-w-xl text-sm leading-relaxed text-text-secondary">
              That is the whole setup. Want to see what it looks like first?
              Explore the live demo with sample data, no install required.
            </p>
          </div>
        </div>
        <Link
          href="/team/"
          className="inline-flex shrink-0 items-center gap-2 border border-accent-cyan bg-accent-cyan px-5 py-2.5 text-sm font-bold text-bg-primary transition-shadow hover:glow-cyan"
        >
          Explore the demo
          <ArrowRight className="h-4 w-4" />
        </Link>
      </section>
    </div>
  );
}
