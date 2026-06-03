import Link from "next/link";
import Image from "next/image";
import {
  Rocket,
  Boxes,
  BookOpen,
  Plug,
  Puzzle,
  Server,
  FileCode,
  Users,
  ArrowRight,
  type LucideIcon,
} from "lucide-react";
import { NAV } from "@/lib/nav";
import { CopyButton } from "@/components/CopyButton";

const ICONS: Record<string, LucideIcon> = {
  Rocket,
  Boxes,
  BookOpen,
  Plug,
  Puzzle,
  Server,
  FileCode,
  Users,
};

const QUICKSTART = `pip install 'horus-os[all]'
horus-os init --interactive
horus-os run "Summarize today's notes and list the open TODOs."`;

export default function Home() {
  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-14 sm:px-10 animate-fade-in">
      {/* Hero */}
      <section className="flex flex-col items-start gap-6 border-b border-border-subtle pb-14">
        <div className="flex items-center gap-3">
          <Image
            src="/horus-eye.svg"
            alt=""
            width={44}
            height={33}
            priority
            className="status-pulse"
          />
          <span className="rounded-full border border-border-subtle bg-bg-secondary px-3 py-1 font-mono text-[11px] uppercase tracking-wider text-text-muted">
            Documentation
          </span>
        </div>

        <h1 className="max-w-3xl text-4xl font-bold leading-[1.1] tracking-tight text-text-primary sm:text-5xl">
          Run a team of AI agents on{" "}
          <span className="text-accent-cyan">your own machine</span>.
        </h1>

        <p
          className="max-w-2xl text-lg leading-relaxed text-text-secondary"
          style={{ fontFamily: "var(--font-sans)" }}
        >
          horus-os is an open-source, self-hosted autonomous AI command center.
          A coordinator breaks down your goals and delegates to specialist
          agents, every action lands in a trace you can read back, and the whole
          stack runs locally, billed to your own API keys. These docs show you
          how to install it, run it, and extend it.
        </p>

        <div className="flex flex-wrap items-center gap-3">
          <Link
            href="/getting-started/introduction/"
            className="inline-flex items-center gap-2 rounded-md bg-accent-cyan px-5 py-2.5 text-sm font-bold text-bg-primary transition-opacity hover:opacity-90"
          >
            Get started
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href="/getting-started/quickstart/"
            className="inline-flex items-center gap-2 rounded-md border border-border-subtle bg-bg-secondary px-5 py-2.5 text-sm font-bold text-text-primary transition-colors hover:border-accent-cyan/40 hover:text-accent-cyan"
          >
            Quickstart
          </Link>
          <a
            href="https://horus-os-demo.vercel.app"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-2 py-2.5 text-sm font-bold text-text-secondary transition-colors hover:text-accent-cyan"
          >
            Live demo
          </a>
        </div>
      </section>

      {/* Quickstart card */}
      <section className="py-12">
        <h2 className="mb-4 text-sm font-bold uppercase tracking-wider text-text-muted">
          Install in three lines
        </h2>
        <div className="overflow-hidden rounded-lg border border-border-subtle bg-[#07080c]">
          <div className="flex items-center justify-between border-b border-border-subtle bg-bg-secondary px-4 py-2">
            <span className="font-mono text-[11px] uppercase tracking-wider text-text-muted">
              bash
            </span>
            <CopyButton
              value={QUICKSTART}
              className="border-transparent bg-transparent px-1.5 py-0.5 hover:bg-bg-elevated"
            />
          </div>
          <pre className="overflow-x-auto px-4 py-4 font-mono text-[13px] leading-relaxed text-text-secondary">
            <code>
              <span className="select-none text-text-muted">$ </span>
              pip install &apos;horus-os[all]&apos;{"\n"}
              <span className="select-none text-text-muted">$ </span>
              horus-os init --interactive{"\n"}
              <span className="select-none text-text-muted">$ </span>
              horus-os run{" "}
              <span className="text-accent-cyan">
                &quot;Summarize today&apos;s notes and list the open TODOs.&quot;
              </span>
            </code>
          </pre>
        </div>
      </section>

      {/* Section cards */}
      <section className="pb-10">
        <h2 className="mb-5 text-sm font-bold uppercase tracking-wider text-text-muted">
          Browse the docs
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {NAV.map((section) => {
            const Icon = ICONS[section.icon];
            const first = section.items[0];
            return (
              <Link
                key={section.label}
                href={`/${first.slug}/`}
                className="group flex flex-col gap-2 rounded-lg border border-border-subtle bg-bg-secondary p-5 transition-all hover:border-accent-cyan/40 hover:bg-bg-elevated border-glow"
              >
                <div className="flex items-center gap-2.5">
                  {Icon && (
                    <Icon className="h-5 w-5 text-accent-cyan" />
                  )}
                  <h3 className="text-base font-bold text-text-primary group-hover:text-accent-cyan">
                    {section.label}
                  </h3>
                </div>
                <p className="text-xs leading-relaxed text-text-muted">
                  {section.items
                    .slice(0, 4)
                    .map((i) => i.title)
                    .join(", ")}
                  {section.items.length > 4 ? ", and more" : ""}
                </p>
              </Link>
            );
          })}
        </div>
      </section>
    </div>
  );
}
