---
title: "Introduction"
description: "horus-os is an open-source, self-hosted autonomous AI command center. Run a team of cooperating AI agents on your own machine, billed to your own keys, with every action traced."
---

horus-os lets one person run a small team of cooperating AI agents from a single
workstation. You give the team a goal through a CLI or a local web dashboard, a
coordinator breaks it down and delegates to specialists, the agents work against
your notes vault and a tool registry, and every action lands in a trace you can
read back. The whole stack runs on your own hardware, billed to your own API
keys, and never requires a cloud account to start.

It is the opposite of a hosted agent service: no account to sign up for, no data
leaving your machine, no vendor lock-in, and no opaque behavior you cannot
inspect.

## What you can do with it

Hand your team a goal in plain language and watch it route the work:

- "Summarize this week's meeting notes and draft a status update." The
  Coordinator pulls the notes and hands the draft to the Writer.
- "Research the top approaches to retrieval-augmented memory, cite sources, and
  save the findings to my vault." The Researcher gathers, summarizes, and writes
  a new note.
- "Read my project notes and list the open risks and decisions." Grounded
  entirely in the markdown vault you control.
- "Which of my tools is failing most often this week?" The Operator reads the
  traces and tells you.

Everything above leaves a trace. Open the dashboard and you can see exactly
which agent did what, which model it called, what it cost, and what it wrote.

## Core values

horus-os is built around four principles. They explain most of the design
decisions you will meet in these docs.

1. **Run on your machine.** The default deployment is a single laptop or home
   server. There is no required SaaS dependency for core operation and no vendor
   lock-in.
2. **Bring your own keys.** AI providers, search providers, integrations, and
   storage backends are all configured through environment variables and a local
   config file. You own every credential.
3. **Inspect everything.** Every agent action writes a trace. Every memory write
   lands in an audit log. There are no hidden subsystems.
4. **Small surface, growable.** A minimal agent runtime ships first; the
   extension points (agents, tools, integrations, plugins, dashboard panels) are
   explicit.

## How the pieces fit

| Layer | What it is |
|-------|------------|
| Agent runtime | Python 3.11+ with the Anthropic and Google Gemini SDKs, plus an optional local OpenAI-compatible provider |
| Persistence | A single SQLite database (WAL mode) on disk |
| Knowledge base | A folder of plain markdown files (your vault), with optional on-device vector search |
| Dashboard | A Next.js app served locally by the runtime (optional; the CLI works without it) |
| Chat surfaces | CLI first, plus opt-in Discord, Slack, Email, and Calendar adapters |

For the full picture, read the [Architecture](/concepts/architecture/) page.

## Named for the all-seeing eye

The Eye of Horus, the Wedjat, was the ancient Egyptian symbol of protection and
watchful oversight. horus-os takes the name seriously: you sit at the center of
the command center, and nothing your agents do is hidden from you. Every
decision, every tool call, and every memory write is visible, attributed, and
reviewable. The agents do the work. The eye is yours.

> [!NOTE]
> horus-os is open source under the Apache 2.0 license. The source lives at
> [github.com/Ridou/horus-os](https://github.com/Ridou/horus-os).

## Where to go next

- [Installation](/getting-started/installation/) installs horus-os and its
  optional extras.
- [Quickstart](/getting-started/quickstart/) takes you from an empty machine to
  a running team in a few minutes.
- [Your first team run](/getting-started/first-team-run/) walks through a real
  task end to end.
- [The agent team](/concepts/agent-team/) explains the coordinator and the
  specialists it delegates to.
