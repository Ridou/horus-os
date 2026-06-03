---
title: "Quickstart"
description: "Go from a fresh machine to a running agent team in minutes. Install horus-os, initialize, run a prompt, and open the dashboard."
---

## Quickstart

This page takes you from nothing to a running agent team in a few minutes: install the package, initialize your data directory, run your first prompt, drive a specific agent, and open the local dashboard. Your API keys stay on your machine the whole way.

For a deeper walkthrough of each step, see [Installation](/getting-started/installation/) and [First team run](/getting-started/first-team-run/).

## Prerequisites

Before you start you need:

- **Python 3.11 or newer.** Check with `python3 --version`.
- **At least one provider API key.** horus-os calls Anthropic Claude and Google Gemini through their official SDKs. You need a key for at least one of them. Grab one from the [Anthropic Console](https://console.anthropic.com/) or [Google AI Studio](https://aistudio.google.com/apikey).

> [!NOTE]
> Your keys are read from your environment and never leave your machine. horus-os is self-hosted: there is no account to sign up for and no cloud service behind it.

## 1. Install

Install the package with the `[all]` extra, which bundles the AI providers and the local dashboard:

```bash
pip install 'horus-os[all]'
```

A bare `pip install horus-os` also runs the full local runtime (the CLI, the agent loop, SQLite storage, the vault, and traces). The `[all]` extra adds the provider SDKs and the dashboard server you will use below. For the complete list of optional extras, see [Installation](/getting-started/installation/).

> [!TIP]
> Install into a virtual environment to keep your system Python clean:
> ```bash
> python3 -m venv .venv && source .venv/bin/activate
> pip install 'horus-os[all]'
> ```

## 2. Initialize

`horus-os init` creates your data directory and seeds a starter team, an example vault, a demo trace, and a sample skill so the CLI and dashboard have something to show immediately.

The fastest path is the interactive setup wizard, which walks you through your API keys and validates them live:

```bash
horus-os init --interactive
```

If you prefer to set the key yourself, run a plain init and export the provider key into your environment:

```bash
horus-os init
export ANTHROPIC_API_KEY=your-api-key
# or, for Gemini:
export GEMINI_API_KEY=your-api-key
```

`init` prints where it put everything: the data directory, the SQLite database, the vault (`notes/`), the skills folder, and the config file. To change where data lives, set `HORUS_OS_DATA_DIR` or pass `--data-dir`. See [Configuration](/getting-started/configuration/) for the defaults on each platform.

> [!NOTE]
> The seeded content is all example data. Rename agents, rewrite their notes, or delete what you do not need. Running your own prompt is how you start replacing it.

## 3. Run your first prompt

Hand your team a goal in plain language. The Coordinator routes the work and synthesizes a single answer:

```bash
horus-os run "Summarize today's notes and list the open TODOs."
```

By default the response streams to your terminal, and the run is recorded as a trace. When it finishes you see a one-line footer with the provider, model, and latency.

A few useful flags on `run`:

- `--no-stream` buffers the full response before printing it, and also reports each tool call.
- `--no-record` skips persisting a trace row for this run.
- `--provider anthropic` or `--provider gemini` overrides the default provider from your config.
- `--model your-model-id` overrides the default model.

```bash
horus-os run --no-stream "Read my project notes and list the open risks."
```

> [!TIP]
> If you see `No API key found`, set `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` in your environment, or re-run `horus-os init --interactive`.

## 4. Drive a specific agent

The starter install creates five agents. List them:

```bash
horus-os agents list
```

You get a table of profiles with their names, models, and a preview of each system prompt. Target one with `--agent` to run a prompt against that agent's persona and tool set:

```bash
horus-os run --agent Researcher "Find three sources on retrieval-augmented memory."
```

To inspect a single agent in detail, use `horus-os agents show <name>`. To learn how the team is structured and how the Coordinator delegates, see [The agent team](/concepts/agent-team/).

## 5. Open the dashboard

Start the bundled local web dashboard:

```bash
horus-os serve
```

By default it binds to `http://127.0.0.1:8765`. Open that URL in a browser to see the team org view, a markdown memory browser, a live activity timeline, the traces explorer, and a costs and observability page. The dashboard talks only to your local backend; there is no hosted service behind it.

Change the bind address with `--host` and `--port`:

```bash
horus-os serve --host 127.0.0.1 --port 9000
```

> [!NOTE]
> `horus-os serve` requires the `[dashboard]` extra, which is included in `[all]`. The dashboard is a static export bundled in the wheel, so end users need no Node and no build step.

## Verify your setup

The fastest confirmation that everything is wired up is simply running a prompt: if `horus-os run` streams an answer, your provider key and config are working.

For deeper diagnostics, `horus-os doctor` checks individual subsystems. Each check is a separate flag, and a bare `horus-os doctor` with no flag just prints the available checks plus a report on your skills folder:

```bash
horus-os doctor
```

Pass a flag to run a specific check:

```bash
# Probe a configured local LLM endpoint and validate its base URL
horus-os doctor --local

# Report on-device vector-memory model and index status
horus-os doctor --memory

# Report configured MCP servers (opt-in via mcp.toml)
horus-os doctor --mcp

# Report the gated shell-execution state and safe working directory
horus-os doctor --shell

# Report per-table RLS status via Supabase PostgREST
horus-os doctor --supabase

# Report whether the always-on service is registered and running
horus-os doctor --service
```

> [!NOTE]
> `horus-os doctor` checks integrations and local subsystems, not your cloud provider keys. The simplest way to confirm an Anthropic or Gemini key is to run a prompt with `horus-os run`. If the key is missing you get a `No API key found` message instead of an answer.

## Next steps

- [First team run](/getting-started/first-team-run/) walks through a full multi-agent task end to end.
- [Configuration](/getting-started/configuration/) covers the data directory, `config.toml`, and provider settings.
- [Installation](/getting-started/installation/) lists every optional extra and platform details.
- [CLI guide](/guides/cli/) covers the full command-line surface.
