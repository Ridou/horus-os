---
title: "Using the dashboard"
description: "Start the local horus-os web dashboard with horus-os serve and tour its pages, from Home, Chat, and Team to Standup, Traces, Costs, and Settings."
---

## What the dashboard is

The dashboard is a local web interface for your horus-os instance. It shows your agents as a team, browses your markdown vault, streams a live activity timeline, and explores every trace, cost, and tool call your team produces. It talks only to your local backend, with no hosted service behind it.

The dashboard is optional. The [CLI](/guides/cli/) drives the full runtime on its own, so you never have to run the dashboard if you prefer the terminal. The two read and write the same data, so anything you do in one shows up in the other.

The dashboard ships as a static Next.js export that is bundled into the wheel, so you run it with no Node and no build step. Node is only needed by contributors who rebuild the dashboard.

> [!NOTE]
> The dashboard requires the `dashboard` extra. It is included in `pip install 'horus-os[all]'`. On a bare install, add it with `pip install 'horus-os[dashboard]'`.

## Starting the dashboard

Start the server with:

```bash
horus-os serve
```

By default it binds to loopback at `http://127.0.0.1:8765`. Open that URL in your browser. The server stays in the foreground; stop it with Ctrl+C.

If you have not initialized your instance yet, run `horus-os init` first so the dashboard has a seeded team, an example vault, and a demo trace to show. See [Installation](/getting-started/installation/) and the [Quickstart](/getting-started/quickstart/) for the full first-run flow.

> [!IMPORTANT]
> The dashboard ships no app-level authentication. Anyone who can reach the URL can use it, and the backend `/api` is unauthenticated. That is why the server binds to loopback (`127.0.0.1`) by default, where only your own machine can reach it. Do not expose it to other machines or the public internet without an authentication layer in front. See [Security](/operations/security/) and [Remote access](/guides/remote-access/).

## A tour of the pages

The sidebar lists the dashboard's pages. Each one is a different view onto the same local instance.

On your first visit the dashboard starts a 10-step onboarding tour: a spotlight overlay highlights each surface in turn and walks you through the pages in order. You can skip it at any step, and replay it any time from the About page.

### Home

The landing view for your instance. It gives you an at-a-glance entry point into the rest of the dashboard.

### Chat

Talk to your team in the browser. Pick an agent (or use the default), watch the reply stream back token by token, and see any tool calls inline; every assistant turn links to the trace it produced. See [Chat](/getting-started/chat/).

### Team

Your agents as an organization. The Team view shows the agent roster (the Coordinator and its specialists) and how they relate, so you can see who delegates to whom. A fresh install seeds five generic agents you can rename, re-persona, or delete. See [The agent team](/concepts/agent-team/).

### Store

The agent store. Install a featured agent bundle in one click, or build a custom agent from a form with no code. Installed agents join your team and are available in chat like any profile you built by hand. See [Agent store](/guides/agent-store/).

### Memory

A browser for your markdown vault. Read and search the notes your agents read and write. The vault is plain markdown on disk, so what you see here matches the files in your data directory. See [The vault](/concepts/the-vault/) and [Editing your vault](/guides/editing-your-vault/).

### Tasks

The view for scheduled and queued work. Use it alongside the CLI to see what the team is set to run. See [Tasks and scheduling](/concepts/tasks-and-scheduling/) and [Scheduling agents](/guides/scheduling-agents/).

### Research

The surface for autonomous research runs, where the team gathers, analyzes, and saves findings to your vault. See [Autonomous research](/guides/autonomous-research/).

### Activity

A live timeline of what every agent did, in order. Use it to watch a run unfold and to review recent actions across the team.

### Standup

The team's reflections surface. A feed of each agent's improvement ideas, wins, risks, and questions, with a Growth tab for shipped wins and a Decisions tab recording what you accepted or dismissed, and why.

### Traces

The traces explorer. Every agent run writes a trace, and this view shows each one with its prompt, the model it called, what it cost, and the tools it used. Parent and child traces let you follow a delegation from the Coordinator down to a specialist. See [Traces and observability](/concepts/traces-and-observability/).

### Costs

A cost and latency overview: spend, latency, and tool reliability across your providers. It is the dashboard companion to the `horus-os usage` CLI command. See [Observability](/operations/observability/).

### Integrations

The status view for your opt-in connectors and integrations. See [Integrations overview](/integrations/overview/).

### Settings

Configuration for your instance, surfaced in the browser.

### About

Build and version information for your dashboard, plus the button that replays the onboarding tour.

## Where the data lives

The dashboard reads from your data directory: the SQLite database for agents, traces, and costs, and the `notes/` vault for memory. See [Configuration](/getting-started/configuration/) for the per-platform data directory locations and the `HORUS_OS_DATA_DIR` override.

## Running it beyond your own machine

By default the dashboard is for the machine it runs on. If you want to reach it from another device, do not just bind it to a public address. horus-os has no built-in auth, so a reachable backend is usable by anyone who can reach it.

- For access from your own devices, use [Remote access](/guides/remote-access/), which keeps the server on its loopback default and reaches it through a private network whose membership is the authentication boundary.
- For a hosted, read-only copy of the dashboard, see [Deploy to Vercel](/operations/deploy-to-vercel/), which serves the static export and reads live data through a safe path. Read the auth prerequisite on that page before deploying anything.

## Next steps

- [Using the CLI](/guides/cli/)
- [Traces and observability](/concepts/traces-and-observability/)
- [Remote access](/guides/remote-access/)
- [Security](/operations/security/)
