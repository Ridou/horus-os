---
title: "Your first team run"
description: "Walk one real task end to end, handing your agent team a plain-language goal and finding the result as a note in your vault with a trace you can read back."
---

## What you will do

In this walkthrough you give your agent team a plain-language goal, let an agent gather material from your vault and write a result back into it, then read the trace of everything that happened. The example task is a common one: summarize your notes and draft a short status update.

This page assumes you have already installed horus-os, run `horus-os init`, and set at least one provider key. If you have not, start with [Installation](/getting-started/installation/) and the [Quickstart](/getting-started/quickstart/).

> [!NOTE]
> A fresh `horus-os init` seeds a five-agent team, about a dozen example notes, and a demo trace, so this walkthrough works against real data on the very first run. Everything is example data you can edit or delete later.

## Step 1: Confirm your team

Every run is handled by an agent profile stored in the local SQLite database. List the seeded team first.

```bash
horus-os agents list
```

You should see five profiles. Each one has a role:

| Agent | Role |
|-------|------|
| Coordinator | Routes a request to the right specialist and synthesizes the results into one answer. |
| Engineer | Handles code and technical work in small, verifiable steps. |
| Researcher | Gathers and analyzes information and summarizes it with sources. |
| Writer | Turns raw material into clear docs, summaries, and content. |
| Operator | Watches the running system for tasks, schedules, errors, and health. |

To inspect a single profile, including its system prompt and which tools it is allowed to call, use `agents show`.

```bash
horus-os agents show Coordinator
```

See [The agent team](/concepts/agent-team/) for the full model of profiles, personas, and delegation.

## Step 2: Hand the team a goal

Give the team a goal in plain language with `horus-os run`. Quote the prompt so your shell passes it as a single argument.

For a task that should actually read your vault and write a note, pass `--no-stream`. This matters: the default `horus-os run` streams the model's tokens straight to your terminal and runs no tools. Only the `--no-stream` (buffered) path executes the built-in tools, so it is the one that can read and write your vault.

```bash
horus-os run --no-stream "Summarize this week's notes and draft a short status update. Save the update as a new note."
```

Because you did not pass `--agent`, the run uses your configured default provider and model. The buffered run executes tools until the agent is done or it hits the iteration cap, prints the final answer, and then lists each tool call it made with its latency.

If you only want a quick conversational answer with no vault access, drop `--no-stream` and the response streams live to your terminal.

```bash
horus-os run "Explain what a status update should contain."
```

To send the goal to a specific agent instead of the default, name it with `--agent`.

```bash
horus-os run --no-stream --agent Researcher "Find three open risks in my project notes and summarize each."
```

Useful flags on `horus-os run`:

| Flag | Effect |
|------|--------|
| `--agent NAME` | Run against a named profile from `horus-os agents`. |
| `--provider anthropic\|gemini` | Override the default provider for this run. |
| `--model MODEL` | Override the default model for this run. |
| `--no-stream` | Buffer the full response, execute the built-in tools, and print a per-tool-call summary at the end. |
| `--no-record` | Do not persist a trace row for this run. |
| `--max-iterations N` | Cap the number of tool-use steps before the buffered loop stops (default 10). |

> [!IMPORTANT]
> The default `horus-os run` is streaming and runs no tools. It cannot read your vault, write a note, or call any other tool. Use `--no-stream` whenever the goal needs the agent to touch the vault or any tool. `--max-iterations` only takes effect on the `--no-stream` path.

## Step 3: How the agent works the goal

On the `--no-stream` path the agent runs a tool-use loop against the built-in tool set. For the example goal that looks like this:

1. The agent reads the goal and recognizes two parts: gather and summarize the notes, then write the status update.
2. It calls the note tools (`list_notes`, `search_notes`, `read_note`) to pull the relevant material from your vault.
3. It drafts the status update from what it read.
4. Because the goal asked for it, it calls `create_note` to save the update as a new markdown file in your vault.
5. It returns a single answer to you, and the per-tool-call summary at the end shows every tool it ran.

The built-in tool set available to a `horus-os run` includes `read_file`, `list_notes`, `search_notes`, `read_note`, `create_note`, `append_note`, and a read-only `github_read`. A skill tool and a gated `shell_exec` tool are added only when you have enabled them.

> [!NOTE]
> The Coordinator's seeded prompt talks about handing work to specialists, but the `delegate_to_agent` tool is not part of the `horus-os run` tool set, so a single `horus-os run` does not spawn sub-agents. Live Coordinator-to-specialist delegation is the autonomous Deep Research feature, which binds a delegation tool and runs the specialists under one shared budget and trace. See [Autonomous research](/guides/autonomous-research/) for that path.

## Step 4: Find the result in your vault

The vault is a plain folder of markdown files inside your data directory (the `notes/` subfolder). When an agent saves a result with `create_note`, it lands there as an ordinary `.md` file you can open in any editor.

Find your data directory and look at the vault. The default location depends on your platform:

- macOS: `~/Library/Application Support/horus-os/notes/`
- Linux: `$XDG_DATA_HOME/horus-os/notes/` or `~/.local/share/horus-os/notes/`
- Windows: `%APPDATA%\horus-os\notes\`

```bash
ls "$HOME/Library/Application Support/horus-os/notes/"
```

The status update the agent drafted will be a new file in that folder. Open it, edit it, or delete it. The vault is yours; horus-os only ever reads and writes plain markdown there, and every write is captured in an audit log so you can see exactly what changed.

> [!NOTE]
> horus-os stores the vault as plain text. It does not parse Obsidian wikilinks, tags, or YAML frontmatter as special metadata. They are kept verbatim as part of the file content.

See [The vault](/concepts/the-vault/) for how memory works and [Editing your vault](/guides/editing-your-vault/) for safe editing practices.

## Step 5: Read the trace

Every recorded run leaves a trace: which agent ran, which model it called, the status, and the prompt. There are two ways to read it back.

### From the CLI

List the most recent traces as a table.

```bash
horus-os traces
```

Narrow the list or switch to machine-readable output:

```bash
# Show the 5 most recent traces
horus-os traces --limit 5

# Emit JSON for scripting
horus-os traces --json
```

The table shows the creation time, provider, model, status, and a preview of the prompt for each run. The JSON form includes the recorded tool uses for each trace. Recorded tool uses come from the buffered `--no-stream` runs; a default streaming run records its prompt and response but no tool calls, because it ran none.

For cost, latency, and tool-reliability rollups across a window, use `horus-os usage` (see the [CLI reference](/reference/cli-reference/)).

### From the dashboard

For a richer view, start the local web dashboard.

```bash
horus-os serve
```

Open the printed address (default `http://127.0.0.1:8765`) and go to the Traces explorer. There you can see each run with its prompt, model, cost, and the tools it called. The Activity timeline shows the same work as a live feed, and the Costs page rolls up spend and latency across providers.

The dashboard talks only to your local backend. There is no hosted service behind it, and no data leaves your machine.

See [Traces and observability](/concepts/traces-and-observability/) for what a trace records and how to read it.

## What you have done

You handed a plain-language goal to your team, ran it with `--no-stream` so the agent read your vault and wrote a result, found that result as a markdown note in your vault, and read the full trace from both the CLI and the dashboard. That is the whole loop: a goal in, traced work, a result you own.

## Next steps

- [The agent team](/concepts/agent-team/): how profiles, personas, and delegation fit together.
- [The vault](/concepts/the-vault/): how your markdown notes become the team's memory.
- [Traces and observability](/concepts/traces-and-observability/): what every run records and how to inspect it.
- [Autonomous research](/guides/autonomous-research/): the path where the Coordinator delegates to specialists.
