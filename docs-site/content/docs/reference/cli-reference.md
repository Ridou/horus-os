---
title: "CLI reference"
description: "Exhaustive reference for every horus-os command, subcommand, and flag, with defaults, exit codes, and short usage examples."
---

## Overview

`horus-os` is the single command-line entry point. Run it with no arguments to print the top-level help, or pass `--version` to print the installed version.

```bash
horus-os --version
horus-os --help
```

| Option | Description |
| ------ | ----------- |
| `--version` | Print the installed horus-os version and exit. |
| `-h`, `--help` | Print help for the program or any subcommand and exit. |

`--help` works at every level: `horus-os schedule --help`, `horus-os schedule create --help`, and so on.

Almost every command accepts `--data-dir PATH` to point at a non-default data directory. When omitted, horus-os resolves the platform default (see [Environment variables](/reference/environment-variables/)). A `--data-dir` flag is documented once per command rather than repeated in every table below.

> [!NOTE]
> Many commands require an initialized installation. Commands that read the SQLite database exit with a non-zero status and the hint `No database at PATH. Run \`horus-os init\` first.` when the database is missing. Run [`horus-os init`](#horus-os-init) once before anything else.

For task-focused walkthroughs, see the [CLI guide](/guides/cli/). The commands below are grouped by area.

## Setup and operation

### horus-os init

Initialize a new installation: create the data directory, write `config.toml`, create the SQLite database, and (on a fresh install only) seed a starter team, example vault notes, an example skill, a demo trace, and demo tasks.

```bash
horus-os init
horus-os init --interactive
```

| Flag | Default | Description |
| ---- | ------- | ----------- |
| `--data-dir PATH` | platform default | Override the data directory. |
| `--force` | off | Overwrite an existing `config.toml`. Does not re-seed starter content. |
| `--interactive` | off | Run the setup wizard with API key onboarding and live validation. |

Running `init` against an already-initialized installation without `--force` or `--interactive` exits non-zero and prints guidance. See [Quickstart](/getting-started/quickstart/) and [Configuration](/getting-started/configuration/).

### horus-os serve

Start the local web dashboard and JSON API. Requires the `dashboard` extra; without it the command exits non-zero and prints the install hint.

```bash
horus-os serve
horus-os serve --host 0.0.0.0 --port 9000
```

| Flag | Default | Description |
| ---- | ------- | ----------- |
| `--host HOST` | `127.0.0.1` | Bind host. |
| `--port PORT` | `8765` | Bind port. |
| `--data-dir PATH` | platform default | Override the data directory. |
| `--disable-all-plugins` | off | Skip plugin discovery entirely. Use this when a misbehaving plugin prevents the server from booting. |

The dashboard serves at `http://127.0.0.1:8765` by default. See the [dashboard guide](/guides/dashboard/) and [Remote access](/guides/remote-access/).

### horus-os doctor

Check integration health and configuration. With no flag, `doctor` prints the available checks and a short skills report, then exits 0. Each flag runs one focused check and sets the exit code based on its result. No flag prints any secret.

> [!NOTE]
> The `--supabase` check does not follow the usual exit-code convention for a negative result. When an expected synced table is missing or has row-level security disabled, it exits `2`, not `1`. A connection or configuration problem (Supabase not configured, `httpx` missing, an RPC error, or an empty result) still exits `1`. The other checks (`--local`, `--service`, `--memory`) exit `1` on a negative result as usual.

```bash
horus-os doctor --local
horus-os doctor --memory
horus-os doctor --mcp
```

| Flag | Description |
| ---- | ----------- |
| `--supabase` | Report per-table row-level-security status via the Supabase PostgREST RPC. Exits 0 only when every expected synced table has RLS enabled; a missing or RLS-disabled table exits `2` (see the note above). |
| `--service` | Report whether the always-on service is registered and running. Exits 0 only when running. |
| `--local` | Validate the configured local LLM base URL (rejecting a wildcard bind) and live-probe the endpoint. |
| `--memory` | Report on-device vector-memory model, index, and mismatch status. Never downloads a model. |
| `--mcp` | Report configured MCP servers from `mcp.toml`. An unconfigured system reports no servers and exits 0. |
| `--shell` | Report the gated shell-execution state and the resolved safe working directory. |
| `--data-dir PATH` | Override the data directory. |

`--supabase` reads `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` from the environment. See [Observability](/operations/observability/) and the integration guides under [Integrations](/integrations/overview/).

## Running agents

### horus-os run

Run a single agent prompt with the configured tools. Output streams by default; the run is recorded as a trace unless you pass `--no-record`.

```bash
horus-os run "Summarize today's notes"
horus-os run "Draft a release note" --agent Writer --no-stream
horus-os run "Quick check" --provider gemini --max-iterations 3
```

| Flag | Default | Description |
| ---- | ------- | ----------- |
| `prompt` | required | Positional. The user prompt to send to the agent. |
| `--provider {anthropic,gemini}` | from config | Override the default LLM provider. |
| `--model NAME` | from config or profile | Override the default model. |
| `--agent NAME` | none | Run against a named agent profile. |
| `--max-iterations N` | `10` | Maximum tool-use iterations before the loop is forced to stop. |
| `--no-record` | off | Do not persist a trace row for this run. |
| `--no-stream` | off | Buffer the full response before printing instead of streaming. |
| `--data-dir PATH` | platform default | Override the data directory. |

If no API key is set for the resolved provider, the command exits non-zero and names the environment variable to set (`ANTHROPIC_API_KEY` or `GEMINI_API_KEY`; `GOOGLE_API_KEY` is accepted as a fallback for Gemini). See [First team run](/getting-started/first-team-run/).

### horus-os agents

Manage agent profiles. With no subcommand, `agents` lists profiles (equivalent to `agents list`).

```bash
horus-os agents list
horus-os agents show Writer
horus-os agents create --name Researcher --system-prompt "You research topics."
```

| Subcommand | Description |
| ---------- | ----------- |
| `list` | List all agent profiles as a table. |
| `show <name>` | Show one profile in detail, including its full system prompt. |
| `create` | Create a new profile. |
| `edit <name>` | Update fields on an existing profile. |
| `delete <name>` | Delete a profile. |

`create` flags:

| Flag | Required | Description |
| ---- | -------- | ----------- |
| `--name NAME` | yes | Profile name. |
| `--system-prompt TEXT` | yes | System prompt for the agent. |
| `--model NAME` | no | Default model for this profile. |
| `--allowed-tools LIST` | no | Comma-separated tool names, or `all` for unrestricted (the default). An empty value denies all tools. |
| `--memory-scope SCOPE` | no | Memory scope for the profile. |

`edit` accepts the same optional flags plus the positional `name`. Only the flags you pass are changed; passing `--allowed-tools all` clears restrictions. See [Agent team](/concepts/agent-team/).

## Skills

### horus-os skills

List and show discoverable skill files under the skills folder. With no subcommand, `skills` lists skills (equivalent to `skills list`). The skills folder is the source of truth, so there is no database to query.

```bash
horus-os skills list
horus-os skills show summarize
```

| Subcommand | Description |
| ---------- | ----------- |
| `list` | List discoverable skills (name, kind, description) and note any files that failed to parse. |
| `show <name>` | Show one skill in detail, including its full body. |

If the skills folder does not exist, `list` suggests running `horus-os init`.

## Memory

### horus-os memory

Manage on-device vector memory. With no subcommand, `memory` prints a usage block listing the operations and exits 0. Vector memory is optional and off by default; it requires the `local-memory` extra.

```bash
horus-os memory download-model
horus-os memory reindex
```

| Subcommand | Description |
| ---------- | ----------- |
| `download-model` | Download the on-device embedding model. This is the only command that triggers a model download (one-time). |
| `reindex` | Rebuild the vector index from existing notes. Reads files only; it creates no notes and writes no audit row. |

`reindex` exits non-zero with a download hint when the embedding model is not yet present. See [The vault](/concepts/the-vault/) and [Autonomous research](/guides/autonomous-research/).

## Scheduling

### horus-os schedule

Manage recurring agent schedules in the `schedules` table. With no subcommand, `schedule` lists schedules (equivalent to `schedule list`). Cron is the canonical stored form; the command accepts a full cron expression, an `@`-alias such as `@daily`, or shorthand sugar such as `every 30m`.

```bash
horus-os schedule create daily-digest --cron "@daily" --profile Writer --prompt "Write the daily digest."
horus-os schedule list
horus-os schedule disable daily-digest
```

| Subcommand | Description |
| ---------- | ----------- |
| `create <name>` | Create a recurring schedule. |
| `list` | List all schedules as a table. |
| `edit <name>` | Update fields on an existing schedule. |
| `delete <name>` | Delete a schedule. |
| `enable <name>` | Enable a schedule. |
| `disable <name>` | Disable a schedule. |

`create` flags:

| Flag | Required | Default | Description |
| ---- | -------- | ------- | ----------- |
| `--cron EXPR` | yes | | Cron expression, an `@`-alias, or sugar such as `every 30m`. |
| `--profile NAME` | yes | | Agent profile to fire on each run. |
| `--prompt TEXT` | yes | | Prompt sent on each run. |
| `--catch-up {coalesce,skip,all}` | no | `coalesce` | How to handle runs missed while the process was down. |

`edit` accepts the positional `name` and the same flags, all optional; only the fields you pass change. An invalid cron expression is rejected before anything is stored. The accepted sugar values are `every 1m`, `every 5m`, `every 30m`, and `every 1h`. See [Scheduling agents](/guides/scheduling-agents/) and [Tasks and scheduling](/concepts/tasks-and-scheduling/).

## Service

### horus-os service

Install and manage the always-on platform-native service. With no subcommand, `service` reports status (equivalent to `service status`).

```bash
horus-os service install
horus-os service install --print
horus-os service status
```

| Subcommand | Description |
| ---------- | ----------- |
| `install` | Register the platform-native service (systemd on Linux, launchd on macOS, nssm on Windows). |
| `uninstall` | Remove the registered service. |
| `start` | Start the registered service. |
| `stop` | Stop the running service. |
| `status` | Report whether the service is registered and running. Exits 0 only when running. |

`install` flags:

| Flag | Description |
| ---- | ----------- |
| `--print` | Print the generated service definition for the current platform without installing it (dry run). |
| `--data-dir PATH` | Override the data directory. |

See [Running as a service](/guides/running-as-a-service/).

## Plugins

### horus-os plugins

Manage installed plugins. With no subcommand, `plugins` prints help. Installs run through a capability-grant flow; review the security model in [Plugin security](/extending/plugin-security/) before installing anything.

```bash
horus-os plugins list
horus-os plugins install ./my-plugin
horus-os plugins grant my-plugin filesystem.read
```

| Subcommand | Description |
| ---------- | ----------- |
| `install <spec>` | Install a plugin from a pip-installable spec (PyPI name, local path, or git URL). |
| `uninstall <name>` | Uninstall an installed plugin. |
| `list` | List installed plugins as a table, or as JSON with `--json`. |
| `info <name>` | Show detailed info for one installed plugin. |
| `enable <name>` | Enable an installed plugin. |
| `disable <name>` | Disable an installed plugin. |
| `update <name> <spec>` | Update a plugin to a new version, running the upgrade-diff classifier. |
| `grant <name> <capability>` | Grant a capability to a plugin. Use `--all` instead of a capability to grant every capability declared in the manifest. |
| `revoke <name> <capability>` | Revoke a capability from a plugin. |

`install` flags:

| Flag | Description |
| ---- | ----------- |
| `--yes`, `-y` | Auto-grant every requested capability without prompting. |
| `--allow-sdist` | Permit sdist installs (runs `setup.py` before manifest validation). Not recommended. |
| `--allow-system-python` | Permit install outside a virtual environment. Not recommended. |

`uninstall` accepts `--yes`/`-y` to skip the confirmation prompt. `list` accepts `--json`. `update` accepts `--yes`/`-y`, `--allow-sdist`, and `--allow-system-python`. `grant` accepts `--all` (mutually exclusive with the positional `capability`, and exactly one is required). See [Plugins](/extending/plugins/) and the [manifest reference](/extending/manifest-reference/).

## Observability

### horus-os traces

List recent agent traces, as a table or JSON.

```bash
horus-os traces
horus-os traces --limit 50 --json
```

| Flag | Default | Description |
| ---- | ------- | ----------- |
| `--limit N` | `20` | Maximum number of traces to display. |
| `--json` | off | Emit machine-readable JSON instead of a table. |
| `--data-dir PATH` | platform default | Override the data directory. |

See [Traces and observability](/concepts/traces-and-observability/).

### horus-os usage

Print a usage report covering cost, latency, and tool reliability over a window, sliced by agent, tool, or model. All cost values round to 6 decimals before output, so the same numbers appear across every format.

```bash
horus-os usage
horus-os usage --since 30d --by model --format json
horus-os usage --by tool --format csv
```

| Flag | Default | Description |
| ---- | ------- | ----------- |
| `--since WINDOW` | `7d` | Window. Accepts `24h`, `7d`, `30d`, or any positive `Nh` or `Nd` form. |
| `--format {json,csv,table}` | `table` | Output shape. |
| `--by {agent,tool,model}` | `agent` | Slice the report. |
| `--data-dir PATH` | platform default | Override the data directory. |

An invalid window exits non-zero with `invalid window: ...` on stderr. The JSON output carries a stable envelope (`by`, `since`, `rows`) with sorted keys so it is diff-stable for downstream scripts. See [Observability](/operations/observability/).

## Exit codes

horus-os commands follow a consistent convention:

| Code | Meaning |
| ---- | ------- |
| `0` | Success, or a healthy/affirmative check result. |
| `1` | A runtime failure or an unhealthy/negative check result (for example, a missing database, a failed run, or a service that is not running). |
| `2` | A usage or configuration error (for example, an unknown provider, an unsupported subcommand, or a missing extra). `horus-os doctor --supabase` also returns `2` for a failed RLS health result (a missing or RLS-disabled synced table), which is the one exception to the code 1 convention above. |

> [!TIP]
> Every numeric value in `horus-os usage` is identical across `--format json`, `csv`, and `table` for the same window, which makes it safe to pipe JSON through `jq` or a table through `column` without precision drift.

## See also

- [CLI guide](/guides/cli/)
- [Configuration reference](/reference/configuration/)
- [Environment variables](/reference/environment-variables/)
- [Getting started: Quickstart](/getting-started/quickstart/)
