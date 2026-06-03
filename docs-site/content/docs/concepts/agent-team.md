---
title: "The agent team"
description: "How horus-os models a small team of cooperating agents, where a Coordinator delegates to specialists, each defined by a SOUL.md persona."
---

## The team mental model

horus-os does not run a single chatbot behind a prompt box. It runs a small team
of cooperating agents, each with a defined role, that hand work back and forth.
You give the team a goal in plain language, and one agent, the Coordinator, breaks
it into steps and delegates each step to the specialist best suited to it. The
specialists do the work and return their results, and the Coordinator synthesizes
those results into one coherent answer.

This shape (a coordinator that routes to specialists) is the core of how horus-os
gets work done. It is also why every run produces a readable trace: you can see
which agent did what, which model it called, and what it wrote. For the broader
runtime picture, see [Architecture](/concepts/architecture/).

## The starter team

A fresh `horus-os init` seeds five generic agents into your database and writes a
persona file for each into your vault. The roster is deliberately generic so you
can rename them, rewrite their personas, add your own, or delete the ones you do
not need.

| Agent | Color | Role |
|-------|:-----:|------|
| Coordinator | `#00d4ff` | Routes a request to the right specialist and synthesizes the results into one answer. |
| Engineer | `#22c55e` | Handles code and technical work in small, verifiable steps. |
| Researcher | `#ec4899` | Gathers and analyzes information and summarizes it with sources. |
| Writer | `#f59e0b` | Turns raw material into clear docs, summaries, and content. |
| Operator | `#a78bfa` | Watches the running system for tasks, schedules, errors, and health. |

Each agent is stored as an agent profile in your local SQLite database. A profile
holds the agent's display name, its system prompt, an optional default model, an
optional list of allowed tools, and the path to its persona file. The starter
profiles leave the model unset on purpose: a seeded agent inherits whatever
provider and model you have configured, which keeps an Anthropic-only or
Gemini-only install from being pinned to the wrong vendor.

> [!NOTE]
> The five-agent team is the floor, not the ceiling. The coordinator-and-specialists
> shape scales well past five. Give a new agent a persona, a color, and a domain,
> and the Coordinator can route to it.

## Personas: the SOUL.md file

Every agent has a persona file named `SOUL.md`. On a fresh install these live in
your vault under `agents/<Name>/SOUL.md`, for example `agents/Coordinator/SOUL.md`.
They are plain markdown, so you can read and edit them with any editor. See
[The vault](/concepts/the-vault/) for where the vault lives on disk and how its
files are stored.

Each `SOUL.md` carries five sections, always in the same order:

- Identity: who the agent is and what it is responsible for.
- Principles: the rules it works by.
- Voice: how it writes and talks.
- Boundaries: what it must not do, and when to escalate to you.
- Workflow: the concrete steps it follows on a task.

Here is the Researcher's persona as it ships, trimmed for length:

```markdown
## Identity

You are the Researcher. You gather information, analyze it, and turn it into a
summary you can trust. You care about where a claim comes from as much as the
claim itself, so every finding carries its source.

## Principles

- Prefer primary references over secondhand summaries.
- Separate what the evidence says from what you infer.
- Cite sources, even briefly, for every nontrivial claim.
- Note the strength of the evidence, not just the conclusion.

## Voice

Clear and measured. You write in plain language, lead with the answer, and
keep the supporting detail tight. You flag uncertainty instead of hiding it.

## Boundaries

- Never fabricate a citation, a quote, or a statistic.
- Never claim certainty beyond what the evidence supports.
- Distinguish a fact from an opinion from a guess.
- Say so plainly when the available sources are thin or conflicting.

## Workflow

1. Restate the question and what a good answer would include.
2. Gather sources and note where each one comes from.
3. Compare them, looking for agreement and contradiction.
4. Summarize the finding with brief citations inline.
5. Call out gaps so you know what is still open.
```

To change how an agent behaves, edit its `SOUL.md`, or update the profile's system
prompt with `horus-os agents edit`. See [Editing your vault](/guides/editing-your-vault/)
for working with vault files directly.

## How the Coordinator delegates

The Coordinator does not do every job itself. It hands subtasks to specialists
through a built-in tool called `delegate_to_agent`. The tool takes two arguments:

- `agent_name`: the name of the agent profile to delegate to.
- `task`: the task or question to send to that sub-agent.

When the Coordinator calls `delegate_to_agent`, horus-os looks up the named profile,
builds a tool registry restricted to that profile's allowed tools, runs the
sub-agent's own loop with its own system prompt, and returns the sub-agent's final
text response back to the Coordinator. The sub-agent's run is recorded as a child
trace linked to the parent, so the dashboard can reconstruct the full delegation
tree. See [Traces and observability](/concepts/traces-and-observability/) for how
those parent and child traces are stored and read back.

A single request can fan out across the team. For example, given "Research the
latest approaches to retrieval-augmented memory and draft a one-page summary," the
Coordinator might delegate the gathering to the Researcher, then hand the
Researcher's findings to the Writer for the draft, then synthesize the final
answer for you.

### Concurrency and the iteration budget

If the Coordinator issues several `delegate_to_agent` calls in the same turn, those
delegations run concurrently. Other tool calls, and a lone delegate call, run
sequentially in order.

To keep a delegation tree from running away, the whole tree shares a single
iteration budget. Every step in the parent and in every sub-agent draws from the
same counter, and the loop stops when the budget is exhausted. You set the ceiling
per run with `--max-iterations` (default `10`):

```bash
horus-os run --max-iterations 20 "Research X, then draft a summary of the findings."
```

### Restricting a sub-agent's tools

A profile can carry an `allowed_tools` list. When set, the sub-agent only sees
those tools. When unset (the default), the sub-agent inherits the unrestricted
registry. This is the security floor for delegation: it limits what a delegated
agent can reach. Inspect a profile's allowed tools with `horus-os agents show`.

> [!NOTE]
> Some powerful tools, such as shell execution, are gated behind both an
> environment flag and an explicit `allowed_tools` entry. An unrestricted profile
> never gains shell access by accident. See [Security](/operations/security/).

## Listing and inspecting agents

Use the `horus-os agents` subcommands to manage the team:

```bash
# List every agent profile (name, model, system-prompt preview)
horus-os agents list

# Show one profile in full, including allowed_tools and the system prompt
horus-os agents show Researcher
```

A truncated `agents show` looks like this:

```text
name:           Researcher
default_model:  (default)
allowed_tools:  (all)
memory_scope:   (none)
system_prompt:
You are the Researcher. You gather and analyze information and summarize it
clearly, citing sources even briefly. ...
```

An `allowed_tools` value of `(all)` means the agent is unrestricted; `(none)`
means it has been explicitly denied every tool.

## Running a specific agent

By default `horus-os run` drives the team. To run a single named agent directly,
pass `--agent`. The run loads that profile's system prompt and tool restrictions:

```bash
# Drive the whole team
horus-os run "Summarize today's notes and list the open TODOs."

# Drive one specialist directly
horus-os run --agent Researcher "Find three sources on retrieval-augmented memory."
```

For a full walkthrough of a first team run, including reading back the trace, see
[Your first team run](/getting-started/first-team-run/).

## Creating and editing agents

You can extend or reshape the team with the create and edit subcommands. A new
agent needs at least a name and a system prompt:

```bash
horus-os agents create \
  --name Analyst \
  --system-prompt "You analyze numeric data and report the key trends with caveats." \
  --model claude-sonnet-4-6 \
  --allowed-tools "read_note,search_notes,list_notes"

horus-os agents edit Analyst --allowed-tools all
horus-os agents delete Analyst
```

The `--allowed-tools` flag takes a comma-separated list of tool names, or the
literal `all` to clear restrictions. To give a new agent a full persona, add a
matching `SOUL.md` under `agents/<Name>/` in your vault.

> [!TIP]
> Models are configurable per agent, so the roster degrades gracefully on a
> single-provider key. Leave a profile's model unset to inherit your configured
> default. See [Configuration](/getting-started/configuration/).

## See also

- [Your first team run](/getting-started/first-team-run/)
- [The vault](/concepts/the-vault/)
- [Traces and observability](/concepts/traces-and-observability/)
- [Architecture](/concepts/architecture/)
