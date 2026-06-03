---
title: "Using the CLI"
description: "A practical tour of the horus-os command line for everyday use, covering init, run, agents, serve, doctor, usage, and the flags you reach for most."
---

## Overview

`horus-os` is the single command you use to set up, run, and operate your install. Every feature in the project has a CLI surface, and most day-to-day work happens here before you ever open the dashboard.

This guide is the friendly tour. It walks through the commands you reach for most and the flags that matter, with short examples. For the exhaustive list of every command, subcommand, and flag, see the [CLI reference](/reference/cli-reference/).

Check your install and version at any time:

```bash
horus-os --version
horus-os
```

Running `horus-os` with no command prints the full help, including every available subcommand.

> [!TIP]
> Almost every command accepts `--data-dir PATH` to point at a non-default data directory. This is handy when you run more than one install side by side, or in tests. When omitted, horus-os uses the platform default. See [Configuration](/getting-started/configuration/) for where that lives.

## init: set up a new install

`horus-os init` creates your data directory, writes a starter `config.toml`, and initializes the SQLite database. Run it once before anything else.

```bash
horus-os init
```

For guided setup with API key onboarding and live validation, use the interactive wizard:

```bash
horus-os init --interactive
```

If a config file already exists, `init` leaves it alone. Pass `--force` to overwrite it:

```bash
horus-os init --force
```

After `init`, set your provider keys as environment variables. horus-os reads `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` from the environment, never from committed files.

```bash
export ANTHROPIC_API_KEY=your-api-key
```

See [Installation](/getting-started/installation/) and [Environment variables](/reference/environment-variables/) for the full setup path.

## run: send a single agent prompt

`horus-os run` executes one agent turn against your configured tools and prints the response. It is the fastest way to test that your install works end to end.

```bash
horus-os run "Summarize the notes in my vault from this week."
```

The agent loop runs tools and iterates until it produces a final answer. By default the response streams to your terminal as it is generated, and a trace row is recorded so you can inspect the run later.

Useful flags:

| Flag | Default | What it does |
| --- | --- | --- |
| `--provider` | from config | Override the LLM provider for this run: `anthropic` or `gemini`. |
| `--model` | from config | Override the model name for this run. |
| `--agent` | none | Run against a named agent profile (see `horus-os agents`). |
| `--max-iterations` | `10` | Cap the number of tool-use iterations before the loop stops. |
| `--no-stream` | off | Buffer the full response and print it once, instead of streaming. |
| `--no-record` | off | Skip writing a trace row for this run. |

Examples:

```bash
# One-off run on a different provider and model
horus-os run "Draft a release note." --provider gemini --model your-model

# Run as a named profile, without recording a trace
horus-os run "Triage today's inbox." --agent researcher --no-record
```

After a run, list what was recorded with `horus-os traces`:

```bash
horus-os traces --limit 10
horus-os traces --json
```

`traces` shows the most recent runs (20 by default). Add `--json` for machine-readable output. To learn how traces fit together, see [Traces and observability](/concepts/traces-and-observability/).

## agents: manage agent profiles

An agent profile bundles a system prompt, an optional model, and a tool allowlist into a reusable identity. Profiles are what `horus-os run --agent <name>` loads.

List and inspect profiles:

```bash
horus-os agents list
horus-os agents show researcher
```

Create a profile:

```bash
horus-os agents create \
  --name researcher \
  --system-prompt "You are a careful research assistant." \
  --allowed-tools all
```

`--allowed-tools` takes a comma-separated list of tool names, or the literal `all` for unrestricted access (the default). You can also set `--model` and `--memory-scope` at creation time.

Edit or remove a profile:

```bash
horus-os agents edit researcher --system-prompt "Be concise and cite sources."
horus-os agents delete researcher
```

To understand how profiles, tools, and the shared vault form a team, read [The agent team](/concepts/agent-team/).

## serve: start the dashboard

`horus-os serve` starts the local web dashboard and JSON API.

```bash
horus-os serve
```

By default it binds to `http://127.0.0.1:8765`. Open that URL in your browser to view traces, costs, agents, and tasks. Change the bind address with `--host` and `--port`:

```bash
horus-os serve --host 127.0.0.1 --port 9000
```

If a misbehaving plugin is preventing the server from booting, skip plugin discovery entirely:

```bash
horus-os serve --disable-all-plugins
```

> [!WARNING]
> The default bind host `127.0.0.1` keeps the dashboard local to your machine. Only change `--host` if you understand the exposure, and put authentication or a tunnel in front of it. See [Remote access](/guides/remote-access/) for safe patterns.

For a full tour of the dashboard, see [Using the dashboard](/guides/dashboard/).

## doctor: check health

`horus-os doctor` reports integration health and configuration status. It runs a focused check based on the flag you pass and never prints any secret.

```bash
horus-os doctor --service     # is the always-on service registered and running
horus-os doctor --local       # probe the configured local LLM endpoint
horus-os doctor --memory      # on-device vector-memory model and index status
horus-os doctor --mcp         # configured MCP servers (opt-in via mcp.toml)
horus-os doctor --shell       # gated shell execution state and safe working dir
horus-os doctor --supabase    # per-table row-level-security status
```

Running `horus-os doctor` with no flag prints the usage block listing the available checks. Each check exits non-zero when something is wrong, so it works well in scripts and pre-flight steps.

Related guides: [Running as a service](/guides/running-as-a-service/), [MCP](/integrations/mcp/), and [Supabase](/integrations/supabase/).

## usage: cost and reliability reports

`horus-os usage` prints a usage report over a time window. Slice it by agent, tool, or model, and render it as a table, JSON, or CSV.

```bash
horus-os usage
horus-os usage --since 30d --by model --format json
horus-os usage --by tool --format csv
```

Flags:

| Flag | Default | What it does |
| --- | --- | --- |
| `--since` | `7d` | Window. Accepts `24h`, `7d`, `30d`, or any `Nh` / `Nd` form. |
| `--by` | `agent` | Slice the report: `agent`, `tool`, or `model`. |
| `--format` | `table` | Output shape: `json`, `csv`, or `table`. |

JSON output uses a stable envelope, so you can pipe it into `jq` or pin it in scripts. Costs are rounded to six decimal places before serialization, and the same numbers appear across all three formats:

```json
{
  "by": "agent",
  "since": "7d",
  "rows": [
    {
      "agent": "default",
      "run_count": 1,
      "total_cache_creation_input_tokens": 0,
      "total_cache_read_input_tokens": 500,
      "total_cost_usd": 0.006150,
      "total_input_tokens": 1000,
      "total_output_tokens": 200,
      "uncosted_runs": 0
    }
  ]
}
```

An invalid window exits non-zero with `invalid window: ...`. If no database exists yet, the command tells you to run `horus-os init` first.

## More commands

The CLI also covers scheduling, the always-on service, skills, plugins, and on-device memory. Each has its own guide:

- `horus-os schedule ...` to create and manage recurring agent runs. See [Scheduling agents](/guides/scheduling-agents/).
- `horus-os service ...` to install and control the background service. See [Running as a service](/guides/running-as-a-service/).
- `horus-os plugins ...` to install, enable, and grant capabilities to plugins. See [Plugins](/extending/plugins/).
- `horus-os memory download-model` and `horus-os memory reindex` for optional on-device vector memory. See [The vault](/concepts/the-vault/).

## Next steps

- [CLI reference](/reference/cli-reference/) for every command and flag
- [Using the dashboard](/guides/dashboard/) for the web view of the same data
- [Run your first team](/getting-started/first-team-run/) for an end-to-end walkthrough
- [Configuration](/getting-started/configuration/) to tune defaults in `config.toml`
