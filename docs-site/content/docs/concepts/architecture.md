---
title: "Architecture"
description: "How horus-os fits together: the agent runtime, providers, SQLite persistence, traces, the vault, the tool registry, adapters, plugins, and the dashboard."
---

## Overview

horus-os is a single self-hosted process that runs a personal team of AI agents on your own machine. The same Python application powers the command line and the local web dashboard. It calls AI providers with your own API keys, stores everything in a single SQLite file, and keeps your knowledge base as plain markdown on disk.

The design follows a few principles end to end:

- **Default to local.** Cloud dependencies are opt-in and replaceable. Your keys, your machine. Nothing about the core runtime requires a hosted service.
- **Explicit tools.** Every capability an agent has is registered, named, and traced. There are no hidden subsystems.
- **Reviewable memory.** Every write to long-term storage is a record you can inspect and revert.
- **No silent network calls.** Outbound traffic happens only when an agent invokes a provider or a tool with explicit network reach.
- **Cross-OS by default.** Releases are gated on Linux, macOS, and Windows continuous integration.

Everything runs in one process by default. The dashboard is served by the same application that backs the CLI's `serve` command, and inbound channels (adapters) mount their routes onto that same application at startup.

## The big picture

```text
   CLI                          Local web dashboard
   horus-os serve   <-------->  http://127.0.0.1:8765
   horus-os doctor              chat + traces + vault + agents
   horus-os init                        |
        |                               v
        |                        FastAPI application
        |                        JSON API + SSE chat stream
        v                               |
   +------------------------------------+------------------+
   |              Agent runtime                            |
   |   single-agent run + multi-turn tool loop             |
   |   coordinator delegation to named sub-agents          |
   +-----------+---------------------------+---------------+
               |                           |
               v                           v
        +-------------+            +-----------------+
        | Providers   |            | Tool registry   |
        | Anthropic   |            | + execution     |
        | Gemini      |            | loop            |
        | local LLM   |            +--------+--------+
        +-------------+                     |
                                            v
                                  +-------------------+
                                  | Tools             |
                                  | vault read/write  |
                                  | delegate_to_agent |
                                  | adapter + plugin  |
                                  | supplied tools    |
                                  +-------------------+

   +-----------------------------+      +---------------------------+
   | SQLite (WAL mode)           |      | The vault                 |
   | traces, note writes,        |      | plain markdown notes/     |
   | agent profiles, schema v13  |      | optional vector memory    |
   +-----------------------------+      +---------------------------+

   +-----------------------------+      +---------------------------+
   | Adapters                    |      | Plugins                   |
   | inbound channels: Discord,  |      | sandboxed extensions      |
   | Slack, Email, Calendar, ... |      | discovered by manifest    |
   +-----------------------------+      +---------------------------+
```

## The agent runtime

The runtime is the core of horus-os. A run starts when a caller asks an agent to act, whether from the CLI, the dashboard chat route, an inbound adapter, or a Python script.

A single run follows a tight loop:

1. **Dispatch.** The runtime picks a provider for the request and builds the initial message list, including the agent's system prompt.
2. **Tool loop.** The provider returns either a final text answer or one or more tool-use requests. The runtime executes each requested tool through the tool registry, appends the results to the conversation, and calls the provider again.
3. **Bounded iteration.** The loop is capped by a maximum iteration count so a run cannot spin forever. This is the safety valve against runaway loops.
4. **Persistence.** Every iteration appends a trace record to SQLite. Tool calls that write to the vault also write a separate note-write record, giving you an audit trail that is independent of the trace log.
5. **Return.** The runtime returns a structured result: the final text, the per-iteration trace, and the tool invocations that ran.

Both synchronous and asynchronous paths exist, and they share the same loop implementation. A streaming path lets the CLI and dashboard show tokens as the provider emits them.

### Multi-agent delegation

A coordinator agent can hand subtasks to named sub-agents using a `delegate_to_agent` tool. Each named agent is an **agent profile**: a stored configuration carrying a name, a system prompt, an optional default model, and an optional list of allowed tools. When a coordinator delegates, the runtime looks up the sub-agent profile, restricts the tool set to what that profile allows, and runs the sub-agent as a nested call.

Two properties keep delegation safe and inspectable:

- **Linked traces.** Trace records carry a parent reference and the profile name they ran as. A coordinator's trace is a root; each sub-agent's trace points back at the coordinator. The dashboard uses this link to render the delegation tree.
- **A shared iteration budget.** The iteration cap is shared across the whole delegation tree rather than applied per sub-agent, so the total amount of work is bounded no matter how the coordinator fans out.

For a deeper look at how agent profiles work, see [the agent team concept](/concepts/agent-team/).

## Providers

horus-os calls AI providers through their official SDKs. Anthropic and Google Gemini are first-class, and an optional on-device local LLM path is available through the `local-llm` extra. Provider credentials are environment variables, never stored in the config file:

```bash
export ANTHROPIC_API_KEY="your-api-key"
export GEMINI_API_KEY="your-api-key"
```

The runtime maps provider responses into a shared internal shape so the rest of the system does not branch on the provider, but it does not hide the underlying differences. Cost, latency, and capability differences between providers are meant to be visible to you. See [environment variables](/reference/environment-variables/) for the full list of provider settings.

## Persistence and the audit trail

State lives in a single SQLite database file inside the data directory, opened in WAL (write-ahead logging) mode for safe concurrent reads and writes. The schema is idempotent and re-applies safely on every boot. The current schema version is 13.

Two record types form the audit trail:

- **Traces.** One row per provider iteration. A trace captures the provider name, the model, the prompt, the completion, the tool calls that ran, latency, and any error, plus the parent reference and profile name for delegated runs.
- **Note writes.** One row per write to the vault. A note write captures a unique write id, the time, the operation (create or append), the target path, the byte size before and after the write, the content that was written, and the id of the trace that produced it. Every write inserts a new row, so the table is a complete, append-only history of vault changes.

The two are deliberately separate. Traces tell you what the agents thought and did. Note writes tell you exactly what they changed on disk, so you can review or revert memory changes without reading the full trace log. Agent profiles are stored in the same database. See [traces and observability](/concepts/traces-and-observability/) for how to read this audit trail.

The default location of the database is inside the data directory:

| OS | Default data directory |
|----|------------------------|
| macOS | `~/Library/Application Support/horus-os` |
| Linux | `$XDG_DATA_HOME/horus-os` or `~/.local/share/horus-os` |
| Windows | `%APPDATA%\horus-os` |

You can override it with the `HORUS_OS_DATA_DIR` environment variable. Inside it you will find `config.toml`, `horus.sqlite`, the `notes/` vault, `skills/`, `models/`, and `vectors.sqlite`. See [configuration](/getting-started/configuration/) for details.

## Traces and the observation surface

Because every iteration writes a trace and every vault change writes a note write, you can reconstruct exactly what happened in any run. The dashboard exposes a traces view, and the runtime serves trace data over its JSON API, including the parent-child links used to render delegation trees.

> [!TIP]
> Traces are the first place to look when an agent does something unexpected. The trace records the prompt, the model, and every tool call, so you can see the decision the model made and the tools it reached for.

See [traces and observability](/concepts/traces-and-observability/) for the conceptual model and [operations/observability](/operations/observability/) for production-facing details.

## The vault and memory layer

The vault is a plain markdown folder (`notes/` inside the data directory). Agents read and write notes through dedicated, registered tools, and every write is recorded as a note write so the change is auditable.

The vault is intentionally plain. horus-os does not parse Obsidian wikilinks, tags, or YAML frontmatter as metadata. Those are stored as ordinary text, which means you can edit the vault in any editor and keep using your own conventions without the runtime reinterpreting them.

Search over the vault is keyword-based by default. An optional on-device vector memory layer adds semantic search and is **off by default**. You opt in by installing the `local-memory` extra (which is not part of `all`), downloading a local embedding model, and indexing the vault:

```bash
pip install 'horus-os[local-memory]'
horus-os memory download-model
horus-os memory reindex
```

Vector data lives in a separate `vectors.sqlite` file so the core database stays portable. See [the vault](/concepts/the-vault/) and [editing your vault](/guides/editing-your-vault/) for more.

## The tool registry

Every capability an agent can use is an explicit, named tool registered in a tool registry. When a provider asks to use a tool, the runtime dispatches the call through the registry, runs the tool, and feeds the result back into the conversation. Tools come from several sources:

- **Built-in tools.** Vault read and write tools, file reading, and the `delegate_to_agent` tool that powers multi-agent runs.
- **Adapter-provided tools.** Some adapters register agent-callable tools when they bind. The Calendar adapter is the canonical example.
- **Plugin-provided tools.** Plugins can contribute tools through their manifest.
- **User-supplied tools.** Callers embedding the runtime in their own Python can register additional callables as tools.

When an agent profile sets a list of allowed tools, the registry is filtered to that subset before the sub-agent runs. This is how delegation enforces least privilege per agent.

## Adapters

Adapters are inbound channels that route external events into the agent runtime. An adapter receives a message from somewhere (a Discord mention, a Slack event, an inbound email, a webhook) and turns it into an agent run, then sends the result back over the same channel.

Adapters are discovered automatically through Python entry points, so the core never needs to know about them at build time. Each adapter binds its own routes onto the FastAPI application at startup. Long-running adapters (those that need a persistent connection or a polling loop) additionally implement lifecycle start and stop hooks tied to the application lifespan. A per-application registry tracks each adapter's live status, and the dashboard exposes a tab to view that status and toggle lifecycle adapters on and off.

Adapter failures are isolated. A broken adapter cannot block startup, shutdown, or the core dashboard. Shipped adapters are all opt-in and lazily import their SDKs, so the package imports cleanly even when an adapter's optional extra is not installed.

See [integrations overview](/integrations/overview/) for the full list of channels and [writing an adapter](/extending/writing-an-adapter/) to build your own.

## Plugins

Plugins extend horus-os with new tools and behavior. A plugin declares what it provides through a manifest. At startup the runtime discovers plugins from two sources: Python entry points in the `horus_os.plugins` group (for pip-installed plugins) and a filesystem directory, which defaults to `~/.horus-os/plugins/` and can be overridden with the `HORUS_OS_PLUGIN_DIR` environment variable. Each subdirectory of the filesystem directory is one plugin, with its `horus-plugin.toml` manifest at the subdirectory root. When the same plugin name appears in both sources, the entry-point version wins. Plugins run under security controls so a third-party extension cannot quietly reach outside its declared surface.

See [plugins](/extending/plugins/) for the plugin model, [plugin security](/extending/plugin-security/) for the sandboxing rules, and [the manifest reference](/extending/manifest-reference/) for the manifest format.

## The dashboard

The local web dashboard is served by the same FastAPI application that backs the CLI. Start it with:

```bash
horus-os serve
```

By default it binds to `http://127.0.0.1:8765`. The dashboard gives you a chat surface, a traces view (including delegation trees), a view of recent vault writes, a read-only view of agent profiles, and an adapters status tab. It speaks to the runtime over a JSON API and a server-sent-events stream for live chat tokens.

> [!IMPORTANT]
> The dashboard has no built-in authentication. Bind it to localhost only, and put it behind a reverse proxy or tunnel if you need remote access. See [remote access](/guides/remote-access/) for safe ways to reach it from another device.

## How the pieces fit together

A typical request flows like this:

1. A request arrives from the CLI, the dashboard chat route, or an adapter.
2. The agent runtime selects a provider and starts the tool loop.
3. The provider may call tools from the registry; vault writes and delegations happen here.
4. Each iteration writes a trace; each vault change writes a note write.
5. The structured result returns to the caller, and the dashboard can replay the whole run from SQLite.

Because state is one SQLite file and one markdown folder, the entire system is portable: copy the data directory and your agents, memory, and history move with it.

## Next steps

- [The agent team](/concepts/agent-team/) for how profiles and delegation work
- [The vault](/concepts/the-vault/) for the markdown memory model
- [Traces and observability](/concepts/traces-and-observability/) for reading the audit trail
- [Plugins](/extending/plugins/) for extending the runtime
