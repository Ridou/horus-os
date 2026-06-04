"use client";

import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  GitBranch,
  HardDrive,
  KeyRound,
  Eye,
  Users,
  Cpu,
  BookText,
  Activity,
  Puzzle,
  Plug,
  LayoutDashboard,
  X,
} from "lucide-react";

/** Public project link. */
const REPO_URL = "https://github.com/Ridou/horus-os";

/** Public community Discord invite. */
const DISCORD_URL = "https://discord.gg/vwX9WvwQhp";

/** Canonical documentation site. */
const DOCS_URL = "https://docs.horus-demo.com";

/** Inline Discord mark (lucide-react ships no brand icons). */
function DiscordMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className={className}
    >
      <path d="M20.317 4.3698a19.7913 19.7913 0 0 0-4.8851-1.5152.0741.0741 0 0 0-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 0 0-.0785-.037 19.7363 19.7363 0 0 0-4.8852 1.515.0699.0699 0 0 0-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 0 0 .0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 0 0 .0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 0 0-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 0 1-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 0 1 .0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 0 1 .0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 0 1-.0066.1276 12.2986 12.2986 0 0 1-1.873.8914.0766.0766 0 0 0-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 0 0 .0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 0 0 .0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 0 0-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z" />
    </svg>
  );
}

/** Value props: why horus-os. Mirrors the static marketing landing. */
const VALUE_PROPS = [
  {
    icon: HardDrive,
    title: "Run on your machine",
    body: "Self-hosted and local first, with SQLite on disk. Your notes, traces, and data never leave your hardware.",
  },
  {
    icon: KeyRound,
    title: "Bring your own keys",
    body: "First-class Anthropic and Gemini support through their official SDKs. No abstraction tax, no required paid account beyond your own LLM key.",
  },
  {
    icon: Eye,
    title: "Inspect everything",
    body: "Every agent run writes a trace. Every memory write lands in an audit log. There is no opaque magic to trust.",
  },
  {
    icon: Users,
    title: "A team, not a chatbot",
    body: "A coordinator delegates to specialists that hand work back and forth, instead of one monolithic model behind a box.",
  },
];

/** The starter team, seeded on install. Colors match the agent roster. */
const TEAM = [
  { name: "Coordinator", color: "#00d4ff", role: "Routes work and synthesizes results" },
  { name: "Engineer", color: "#22c55e", role: "Code, in small verifiable steps" },
  { name: "Researcher", color: "#ec4899", role: "Sources, analysis, summaries" },
  { name: "Writer", color: "#f59e0b", role: "Clear docs and content" },
  { name: "Operator", color: "#a78bfa", role: "Runtime, schedules, health" },
];

/** Features grid: what is inside the runtime. */
const FEATURES = [
  {
    icon: Cpu,
    title: "Two providers",
    body: "Anthropic Claude and Google Gemini through official SDKs, no abstraction layer.",
  },
  {
    icon: BookText,
    title: "Tools and memory",
    body: "A tool registry plus a markdown notes vault the agents read and write, with audited writes.",
  },
  {
    icon: Activity,
    title: "Observability",
    body: "Per-run cost, latency, and tool-reliability tracking, with a costs dashboard and a usage CLI.",
  },
  {
    icon: Puzzle,
    title: "Plugin system",
    body: "Third-party tools and adapters from a manifest, with default-deny capability grants.",
  },
  {
    icon: Plug,
    title: "Adapters",
    body: "Opt-in connectors for Discord, Slack, Email, and Calendar so agents act on surfaces you pick.",
  },
  {
    icon: LayoutDashboard,
    title: "Local dashboard",
    body: "A team view, memory browser, activity, traces, and costs, bundled in the wheel. No Node to run it.",
  },
];

/** What horus-os deliberately is not. */
const IS_NOT = [
  "A hosted SaaS or an account you sign up for",
  "A service that ships your data to a third party",
  "A single monolithic model behind a chat box",
  "Locked to one LLM vendor",
];

/** A small reusable section eyebrow + heading. */
function SectionHead({
  eyebrow,
  title,
  lead,
}: {
  eyebrow: string;
  title: string;
  lead?: string;
}) {
  return (
    <div className="max-w-2xl">
      <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-accent-cyan">
        {eyebrow}
      </span>
      <h2 className="mt-2.5 text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">
        {title}
      </h2>
      {lead && (
        <p className="mt-2.5 text-sm leading-relaxed text-text-secondary">
          {lead}
        </p>
      )}
    </div>
  );
}

/**
 * Demo-mode marketing landing. Ports the content and cyber, cyan-on-near-black
 * style of the static site into the dashboard design system. Rendered at "/"
 * only when demo mode is active, so a local install opens straight into the
 * dashboard.
 */
export function MarketingLanding() {
  return (
    <div className="mx-auto max-w-5xl">
      {/* Top bar: wordmark + quick links */}
      <nav className="flex items-center justify-between py-2">
        <span className="flex items-center gap-2.5">
          <Image
            src="/horus-eye.svg"
            alt="horus-os"
            width={28}
            height={21}
            priority
            className="status-pulse"
          />
          <span className="text-base font-bold tracking-tight text-text-primary">
            horus<span className="text-accent-cyan">-os</span>
          </span>
        </span>
        <span className="flex items-center gap-5 text-xs text-text-secondary">
          <a href="#why" className="hidden transition-colors hover:text-accent-cyan sm:inline">
            Why
          </a>
          <a href="#team" className="hidden transition-colors hover:text-accent-cyan sm:inline">
            Team
          </a>
          <a href="#features" className="hidden transition-colors hover:text-accent-cyan sm:inline">
            Features
          </a>
          <Link
            href={DOCS_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 transition-colors hover:text-accent-cyan"
          >
            <BookText className="h-3.5 w-3.5" />
            Docs
          </Link>
          <Link
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 transition-colors hover:text-accent-cyan"
          >
            <GitBranch className="h-3.5 w-3.5" />
            GitHub
          </Link>
          <Link
            href={DISCORD_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 transition-colors hover:text-accent-cyan"
          >
            <DiscordMark className="h-3.5 w-3.5" />
            Community
          </Link>
        </span>
      </nav>

      {/* Hero */}
      <header className="flex flex-col items-center gap-0 border border-border-subtle bg-bg-secondary px-6 py-14 text-center gradient-cyber sm:py-16">
        <Image
          src="/horus-eye.svg"
          alt="horus-os"
          width={88}
          height={66}
          priority
          className="status-pulse glow-cyan mb-7"
        />
        <h1 className="text-3xl font-extrabold leading-tight tracking-tight text-text-primary sm:text-5xl">
          Your self-hosted, all-seeing
          <br />
          AI command center.
        </h1>
        <p className="mt-5 max-w-xl text-sm leading-relaxed text-text-secondary sm:text-base">
          horus-os runs a small team of cooperating AI agents on your own
          machine. Bring your own keys, inspect every action, own your data. No
          SaaS, no lock-in.
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/team/"
            className="inline-flex items-center gap-2 border border-accent-cyan bg-accent-cyan px-5 py-2.5 text-sm font-semibold text-bg-primary transition-shadow hover:glow-cyan"
          >
            Launch the demo
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href="/get-started/"
            className="inline-flex items-center gap-2 border border-border-subtle bg-bg-elevated px-5 py-2.5 text-sm font-semibold text-text-primary transition-colors hover:border-accent-cyan/50"
          >
            Get started
          </Link>
          <Link
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 border border-border-subtle bg-bg-elevated px-5 py-2.5 text-sm font-semibold text-text-primary transition-colors hover:border-accent-cyan/50"
          >
            <GitBranch className="h-4 w-4" />
            GitHub
          </Link>
          <Link
            href={DISCORD_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 border border-border-subtle bg-bg-elevated px-5 py-2.5 text-sm font-semibold text-text-primary transition-colors hover:border-accent-cyan/50"
          >
            <DiscordMark className="h-4 w-4" />
            Community
          </Link>
        </div>

        <div className="mt-7 inline-flex flex-wrap items-center justify-center gap-3 border border-border-subtle bg-bg-primary px-4 py-2.5 text-sm text-text-secondary">
          <code className="text-accent-cyan">pip install &apos;horus-os[all]&apos;</code>
          <span className="text-text-muted">then</span>
          <code className="text-accent-cyan">horus-os init</code>
        </div>
      </header>

      {/* Why */}
      <section id="why" className="mt-12 scroll-mt-6">
        <SectionHead
          eyebrow="Why horus-os"
          title="Built to be owned, not rented."
          lead="It is the opposite of a hosted agent service. Everything runs locally, and nothing is hidden from you."
        />
        <div className="mt-7 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {VALUE_PROPS.map((prop) => {
            const Icon = prop.icon;
            return (
              <div
                key={prop.title}
                className="flex flex-col gap-2 border border-border-subtle bg-bg-secondary p-5 border-glow"
              >
                <div className="flex items-center gap-2.5">
                  <Icon className="h-4 w-4 shrink-0 text-accent-cyan" />
                  <h3 className="text-sm font-bold text-text-primary">
                    {prop.title}
                  </h3>
                </div>
                <p className="text-[13px] leading-relaxed text-text-secondary">
                  {prop.body}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Team */}
      <section id="team" className="mt-12 scroll-mt-6">
        <SectionHead
          eyebrow="Starter team"
          title="Five agents, seeded on install."
          lead="A fresh install creates a team with persona files you can rewrite, plus an example vault so nothing is empty on first run."
        />
        <div className="mt-7 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {TEAM.map((agent) => (
            <div
              key={agent.name}
              className="flex flex-col items-center gap-2.5 border border-border-subtle bg-bg-secondary p-4 text-center border-glow"
            >
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: agent.color }}
              />
              <span className="text-sm font-bold text-text-primary">
                {agent.name}
              </span>
              <span className="text-[11px] leading-snug text-text-muted">
                {agent.role}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="mt-12 scroll-mt-6">
        <SectionHead eyebrow="What is inside" title="A complete local agent runtime." />
        <div className="mt-7 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => {
            const Icon = feature.icon;
            return (
              <div
                key={feature.title}
                className="flex flex-col gap-2 border border-border-subtle bg-bg-secondary p-5 border-glow"
              >
                <div className="flex items-center gap-2.5">
                  <Icon className="h-4 w-4 shrink-0 text-accent-cyan" />
                  <h3 className="text-sm font-bold text-text-primary">
                    {feature.title}
                  </h3>
                </div>
                <p className="text-[13px] leading-relaxed text-text-secondary">
                  {feature.body}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* What it is not */}
      <section id="not" className="mt-12">
        <SectionHead eyebrow="Set expectations" title="What horus-os is not." />
        <div className="mt-6 grid grid-cols-1 gap-x-7 gap-y-2.5 sm:grid-cols-2">
          {IS_NOT.map((item) => (
            <div
              key={item}
              className="flex items-start gap-2 text-sm leading-relaxed text-text-secondary"
            >
              <X className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" />
              {item}
            </div>
          ))}
        </div>
      </section>

      {/* Closing CTA */}
      <section className="mt-12 border border-border-subtle bg-bg-secondary p-6 text-center gradient-cyber sm:p-8">
        <h2 className="text-xl font-bold tracking-tight text-text-primary sm:text-2xl">
          Ready to look inside?
        </h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-text-secondary">
          Explore the live demo with sample data, or install horus-os and run
          your own agents with your own keys.
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/team/"
            className="inline-flex items-center gap-2 border border-accent-cyan bg-accent-cyan px-5 py-2.5 text-sm font-semibold text-bg-primary transition-shadow hover:glow-cyan"
          >
            Launch the demo
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href="/get-started/"
            className="inline-flex items-center gap-2 border border-border-subtle bg-bg-elevated px-5 py-2.5 text-sm font-semibold text-text-primary transition-colors hover:border-accent-cyan/50"
          >
            Get started
          </Link>
          <Link
            href={DISCORD_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 border border-border-subtle bg-bg-elevated px-5 py-2.5 text-sm font-semibold text-text-primary transition-colors hover:border-accent-cyan/50"
          >
            <DiscordMark className="h-4 w-4" />
            Join the community
          </Link>
        </div>
        <p className="mt-4 text-xs text-text-muted">
          Questions or stuck on setup? The #help forum on Discord is a
          searchable Q&amp;A.
        </p>
      </section>

      {/* Footer */}
      <footer className="mt-12 border-t border-border-subtle py-8 text-center text-xs text-text-muted">
        <p className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1">
          <Link
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-text-secondary transition-colors hover:text-accent-cyan"
          >
            GitHub
          </Link>
          <span aria-hidden="true">.</span>
          <Link
            href={DOCS_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-text-secondary transition-colors hover:text-accent-cyan"
          >
            Docs
          </Link>
          <span aria-hidden="true">.</span>
          <Link
            href="/team/"
            className="text-text-secondary transition-colors hover:text-accent-cyan"
          >
            Live demo
          </Link>
          <span aria-hidden="true">.</span>
          <Link
            href={DISCORD_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-text-secondary transition-colors hover:text-accent-cyan"
          >
            Community
          </Link>
          <span aria-hidden="true">.</span>
          <span>Apache 2.0</span>
        </p>
        <p className="mt-2">
          horus-os runs entirely on your own hardware. This page is a static
          showcase with no backend.
        </p>
      </footer>
    </div>
  );
}

export default MarketingLanding;
