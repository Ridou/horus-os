# Architecture

This document describes the actual shape of `horus-os` as shipped in
v0.1.0. For project intent and what is out of scope, see `PROJECT.md`.

## Top-level shape

```
  +-------------------+        +-----------------------+
  |  CLI              |        |  Local web dashboard  |
  |  horus-os run     |        |  127.0.0.1:8765       |
  |  horus-os init    |        |  chat + traces +      |
  |  horus-os traces  |        |  writes audit         |
  |  horus-os serve   |        +----------+------------+
  +---------+---------+                   |
            |                             v
            |                  +-----------------------+
            |                  |  FastAPI app          |
            |                  |  /api/health          |
            |                  |  /api/chat            |
            |                  |  /api/traces[/{id}]   |
            |                  |  /api/writes          |
            |                  +----------+------------+
            |                             |
            v                             v
        +------------------------------------+
        |  Agent runtime (horus_os.agent)    |
        |  run_agent / run_agent_async       |
        |  run_agent_loop                    |
        +------+--------------+--------------+
               |              |
               v              v
        +-----------+   +-------------+
        | Providers |   | Tool        |
        | Anthropic |   | registry +  |
        | Gemini    |   | loop        |
        +-----------+   +-------------+
                               |
                               v
                       +----------------+
                       | Tools          |
                       | read_file      |
                       | notes (6)      |
                       | user-supplied  |
                       +----------------+

                +----------------------------+
                |  SQLite (horus_os.storage) |
                |  WAL mode, schema v2       |
                |  traces, note_writes       |
                +----------------------------+
```

Everything runs in a single process by default. The dashboard is
served by the same FastAPI app that powers the CLI's `serve`
subcommand. There is no separate frontend build; the dashboard is
single-page vanilla JS shipped as a package data file.

## Module layout

`src/horus_os/`

| Module | Role |
|--------|------|
| `agent.py` | Runtime entry points: `run_agent`, `run_agent_async`, `run_agent_loop`. Owns the multi-turn tool-execution loop. |
| `_providers/_anthropic.py` | Anthropic Claude bindings. Sync and async calls, plus a `Conversation` class for stateful multi-turn use. |
| `_providers/_gemini.py` | Google Gemini bindings. Same surface as Anthropic. |
| `tools/registry.py` | `ToolRegistry`, `execute_tool_uses`. Registers callables as tools and dispatches model-issued tool calls. |
| `tools/loop.py` | The multi-step tool-execution loop. Bounded by `max_iterations`. |
| `tools/builtin.py` | Built-in tool factories. `read_file_tool` is the canonical example. |
| `memory/notes.py` | `NotesStore` over a markdown folder. List, search, read, create, append. |
| `memory/tools.py` | Tool factories that expose the notes store to an agent. |
| `storage.py` | `Database`, `TraceRecord`, `NoteWrite`. SQLite with WAL mode and idempotent migrations. |
| `server/api.py` | FastAPI app. JSON API plus the static dashboard. |
| `cli/` | Argparse subcommands: `init`, `run`, `serve`, `traces`. The `init` subcommand supports `--interactive` for the setup wizard. |
| `config.py` | Config file location, load, and save. Honors `HORUS_OS_HOME` for the data directory. |
| `types.py` | Shared dataclasses and type aliases used across modules. |

`tests/` mirrors `src/horus_os/` one to one. Every public surface is
covered.

## Data flow: a single agent run

1. **Entry.** Caller invokes `run_agent(prompt, ...)` from the CLI,
   the dashboard's `/api/chat` route, or a Python script.
2. **Provider dispatch.** The runtime picks Anthropic or Gemini based
   on the request, instantiates the provider client, and constructs
   the initial message list.
3. **Tool loop.** The provider returns either a final text answer or
   one or more tool-use blocks. The loop executes each tool through
   the registry, appends the results to the conversation, and calls
   the provider again. The loop bails at `max_iterations` (default 10).
4. **Persistence.** Every iteration appends a `TraceRecord` to SQLite.
   Tool calls that write to the notes folder also write a `NoteWrite`
   row, giving the user a reviewable audit trail independent of the
   trace log.
5. **Return.** The runtime returns a structured result: final text,
   per-iteration trace, and any tool invocations that ran.

The async path (`run_agent_async`) mirrors the sync path; both routes
share the loop implementation.

## Storage shape

SQLite, single file, WAL mode, 5000ms busy timeout. Schema is
idempotent and re-applies safely on every boot.

Two main tables matter for v0.1:

- `traces`: one row per provider iteration. Captures provider name,
  model, prompt, completion, tool calls, latency, error if any.
- `note_writes`: one row per write to the markdown notes folder.
  Captures source agent run, target path, write mode (create or
  append), payload, and a hash for de-duplication.

The path to the database is configurable. The default lives under the
data directory chosen by `init` (`~/.local/share/horus-os/` on Linux,
`~/Library/Application Support/horus-os/` on macOS,
`%LOCALAPPDATA%/horus-os/` on Windows).

## Configuration

`horus-os init` creates a config file in the platform-specific config
directory. Environment variables override file values. The wizard
(`init --interactive`) walks the user through:

1. Choosing a data directory.
2. Choosing a notes directory.
3. Supplying Anthropic and/or Gemini API keys.
4. Validating each key with a single live token request before
   saving.

The config file stores non-secret defaults: data directory, notes
directory, default provider, default model, default max iterations.
Keys live in environment variables.

## Provider model

Both providers are called through their official SDKs without an
intervening abstraction layer. The runtime exposes a thin internal
adapter that maps provider responses into a shared
`ProviderResponse` shape, but the SDK objects themselves are not
hidden from advanced callers. This is a deliberate choice: cost,
latency, and capability differences should be visible.

To add a third provider, see `CONTRIBUTING.md` under "How to add a
new provider."

## Design principles

1. **Default to local.** Cloud dependencies are opt-in and
   replaceable. The user's own keys, the user's own machine.
2. **Explicit tools.** Every capability the agent has is registered,
   named, and traced. No "magic" subsystems.
3. **Reviewable memory.** Every write to long-term storage is a
   record the user can inspect and revert.
4. **No silent network calls.** Outbound traffic happens only when
   the agent invokes a provider or a user-supplied tool with explicit
   network reach.
5. **Cross-OS by default.** Three-OS CI gates every release. Paths
   are `pathlib`; subprocess invocations are minimized; line endings
   are normalized.

## What is not in v0.1

- **Streaming responses.** The dashboard waits for the full loop to
  finish before rendering.
- **Multi-agent orchestration.** A single agent answers per request.
  Multi-agent is the v0.2 milestone.
- **Vector search.** Notes search is keyword-based for v0.1. A vector
  store is on the v0.2+ list.
- **Authentication on the dashboard.** Bind to `127.0.0.1` only.
- **Retry, rate-limit handling, cost tracking.** Deferred to a later
  observability milestone.

See `ROADMAP.md` for what is planned next.
