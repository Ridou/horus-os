# Architecture

This document describes the actual shape of `horus-os` on the `main`
branch heading into v0.2.0. For project intent and what is out of
scope, see `PROJECT.md`. For the v0.1 to v0.2 upgrade path, see
`docs/MIGRATION-v0.1-to-v0.2.md`.

## Top-level shape

```
  +-------------------+        +-----------------------+
  |  CLI              |        |  Local web dashboard  |
  |  horus-os run     |        |  127.0.0.1:8765       |
  |  horus-os init    |        |  chat + traces +      |
  |  horus-os traces  |        |  writes + agents      |
  |  horus-os agents  |        +----------+------------+
  |  horus-os serve   |                   |
  +---------+---------+                   v
            |                  +-----------------------+
            |                  |  FastAPI app          |
            |                  |  /api/health          |
            |                  |  /api/chat            |
            |                  |  /api/chat/stream     |
            |                  |  /api/traces[/{id}]   |
            |                  |  /api/traces/{id}/children |
            |                  |  /api/writes          |
            |                  |  /api/agents[/{name}] |
            |                  |  /api/adapters/...    |
            |                  +----------+------------+
            |                             |
            v                             v
        +------------------------------------+
        |  Agent runtime (horus_os.agent)    |
        |  run_agent / run_agent_async       |
        |  run_agent_loop                    |
        |  run_agent_stream                  |
        +------+--------------+--------------+
               |              |
               v              v
        +-----------+   +-------------+
        | Providers |   | Tool        |
        | Anthropic |   | registry +  |
        | Gemini    |   | loop +      |
        +-----------+   | delegation  |
                        +-------------+
                               |
                               v
                       +----------------+
                       | Tools          |
                       | read_file      |
                       | notes (6)      |
                       | delegate_to_   |
                       |   agent        |
                       | user-supplied  |
                       +----------------+

                +----------------------------+
                |  SQLite (horus_os.storage) |
                |  WAL mode, schema v4       |
                |  traces (parent_trace_id,  |
                |   agent_profile_name),     |
                |  note_writes,              |
                |  agent_profiles            |
                +----------------------------+

                +----------------------------+
                |  Adapters                  |
                |  Adapter Protocol +        |
                |  entry-point discovery     |
                |  WebhookAdapter (ref)      |
                +----------------------------+
```

Everything runs in a single process by default. The dashboard is
served by the same FastAPI app that powers the CLI's `serve`
subcommand. There is no separate frontend build; the dashboard is
single-page vanilla JS shipped as a package data file. Adapters are
mounted at app startup via `discover_adapters()` and bind their own
routes onto the FastAPI instance.

## Module layout

`src/horus_os/`

| Module | Role |
|--------|------|
| `agent.py` | Runtime entry points: `run_agent`, `run_agent_async`, `run_agent_loop`, `run_agent_stream`. Owns the multi-turn tool-execution loop. |
| `_providers/_anthropic.py` | Anthropic Claude bindings. Sync, async, and streaming async calls, plus a `Conversation` class that honors a per-profile `system_prompt`. |
| `_providers/_gemini.py` | Google Gemini bindings. Same surface as Anthropic. |
| `tools/registry.py` | `ToolRegistry`, `execute_tool_uses`. Registers callables as tools and dispatches model-issued tool calls. |
| `tools/loop.py` | The multi-step tool-execution loop. Bounded by `max_iterations` or by a shared `IterationBudget` when delegation is in play. |
| `tools/builtin.py` | Built-in tool factories. `read_file_tool` is the canonical example. |
| `tools/delegation.py` | `IterationBudget`, `_filter_registry`, `make_delegate_tool`. The delegation primitives the multi-agent runtime is built on. |
| `memory/notes.py` | `NotesStore` over a markdown folder. List, search, read, create, append. |
| `memory/tools.py` | Tool factories that expose the notes store to an agent. |
| `storage.py` | `Database`, `TraceRecord`, `NoteWrite`, `AgentProfile` CRUD. SQLite with WAL mode and idempotent migrations through v4. |
| `server/api.py` | FastAPI app. JSON API, SSE chat stream, and the static dashboard. Calls `discover_adapters()` at app startup and binds each one. |
| `cli/` | Argparse subcommands: `init`, `run`, `serve`, `traces`, `agents`. The `init` subcommand supports `--interactive` for the setup wizard; `run` streams by default with `--no-stream` for the v0.1 behavior. |
| `adapters/base.py` | `Adapter` Protocol, `AdapterContext`, `discover_adapters`, `ADAPTER_ENTRY_POINT_GROUP`. |
| `adapters/webhook.py` | Reference `WebhookAdapter`: HMAC-SHA256 signed HTTP webhook receiver mounted at `/api/adapters/webhook`. |
| `config.py` | Config file location, load, and save. Honors `HORUS_OS_HOME` for the data directory. |
| `types.py` | Shared dataclasses and type aliases: `Tool`, `ToolUse`, `ToolResult`, `ToolCallEvent`, `AgentResult`, `AgentProfile`, `NoteRef`, `NoteWrite`. |

`tests/` mirrors `src/horus_os/` one to one. Every public surface is
covered. The suite is at 302 passing tests heading into Phase 18.

## Data flow: a single agent run

1. **Entry.** Caller invokes `run_agent(prompt, ...)` from the CLI,
   the dashboard's `/api/chat` route, or a Python script.
2. **Provider dispatch.** The runtime picks Anthropic or Gemini based
   on the request, instantiates the provider client, and constructs
   the initial message list.
3. **Tool loop.** The provider returns either a final text answer or
   one or more tool-use blocks. The loop executes each tool through
   the registry, appends the results to the conversation, and calls
   the provider again. The loop bails when the iteration budget is
   exhausted (default 10).
4. **Persistence.** Every iteration appends a `TraceRecord` to SQLite.
   Tool calls that write to the notes folder also write a `NoteWrite`
   row, giving the user a reviewable audit trail independent of the
   trace log.
5. **Return.** The runtime returns a structured result: final text,
   per-iteration trace, and any tool invocations that ran.

The async path (`run_agent_async`) mirrors the sync path; both routes
share the loop implementation.

## Multi-agent shape

A coordinator agent can hand off subtasks to named sub-agents via the
`delegate_to_agent` tool. Profiles are rows in the `agent_profiles`
table; the runtime looks them up by name on every delegation.

1. **AgentProfile.** Stored as a row in `agent_profiles`. Carries
   `name`, `system_prompt`, optional `default_model`, optional
   `allowed_tools` (None means unrestricted), and optional
   `memory_scope` (opaque, reserved for later use). `init()`
   bootstraps a default profile so a fresh database always has at
   least one row.
2. **make_delegate_tool.** A factory in `tools/delegation.py` that
   produces a `Tool` whose handler looks up a sub-agent profile,
   filters the master registry by the profile's `allowed_tools`, and
   calls `run_agent_loop` with the profile's `system_prompt`. The
   coordinator runs as the top-level call; each delegated turn writes
   its own trace row.
3. **Parent and child traces.** The `traces` table carries
   `parent_trace_id` and `agent_profile_name`. The coordinator's trace
   has both columns null. Each sub-agent trace points at the
   coordinator's `trace_id` and records the profile name it ran as.
   `Database.list_child_traces(parent_trace_id)` returns the children
   oldest first; the dashboard uses it to render delegate trees.
4. **Shared iteration budget.** `IterationBudget` is a thread-safe
   counter created at the top-level `run_agent_loop` and passed by
   reference into every nested call. `consume()` decrements under a
   lock, so the cap applies across the whole tree rather than per
   sub-agent. This is the safety valve against runaway recursion.
5. **Parallel delegation.** When the coordinator emits two or more
   `delegate_to_agent` calls in one turn, `execute_tool_uses` runs
   them through a bounded `ThreadPoolExecutor` and matches results
   back to requests by `tool_use_id`.

## Streaming surface

`run_agent_stream` is an async generator added in Phase 14. It yields
`str` tokens as the provider emits them, then any `ToolCallEvent`
values observed in the final assembled response. Tool execution is
intentionally not handled here; streaming and tool dispatch do not
compose in a single pass without buffering, which negates the
streaming win.

- **Provider helpers.** `stream_anthropic_async` (uses
  `messages.stream`) and `stream_gemini_async` (uses
  `generate_content_stream`) both yield `str` deltas. Empty chunks
  from Gemini are gated so consumers see only real tokens.
- **ToolCallEvent emission.** A synthetic event type defined in
  `types.py`. Both provider helpers emit any tool requests they see
  after the text stream drains so consumers observe a consistent
  shape: text first, then tool calls.
- **CLI consumption.** `horus-os run "..."` consumes the generator
  via `asyncio.run` of an inner coroutine that writes tokens to
  `stdout` and `ToolCallEvent`s to `stderr`. `--no-stream` falls back
  to the v0.1 buffered behavior.
- **Dashboard consumption.** `POST /api/chat/stream` returns
  `text/event-stream`. Each frame is `data: <json>\n\n` with a `type`
  discriminator (`token`, `tool_call`, `done`, `error`). The dashboard
  appends tokens to a `<pre>` via `appendChild(createTextNode(...))`
  so the XSS boundary stays intact.

## Adapter interface

Adapters are inbound channels that route external events into the
agent runtime. The contract is defined in `horus_os.adapters` and
discovery is driven by Python's `importlib.metadata.entry_points`.

- **Adapter Protocol.** A `runtime_checkable` Protocol from
  `adapters/base.py` requiring a `name: str` attribute and a
  `bind(app, context) -> None` method. An optional `describe()`
  method may return a static metadata dict for diagnostics.
- **AdapterContext.** A frozen dataclass passed to `bind`. Carries
  the resolved `Config` and the resolved `data_dir`. Adapters store
  whatever subset they need.
- **discover_adapters.** Walks `entry_points(group="horus_os.adapters")`,
  sorts by name, instantiates each entry (class, factory, or
  pre-built instance), returns the list. Per-entry failures are
  caught and isolated so a broken adapter cannot brick the core
  dashboard.
- **Entry-point registration.** Third-party packages declare an
  adapter in their `pyproject.toml`:

  ```
  [project.entry-points."horus_os.adapters"]
  my_adapter = "my_package.adapter:MyAdapter"
  ```

  After `pip install`, the adapter is discovered automatically the
  next time `create_app` runs.
- **Reference adapter.** `WebhookAdapter` lives in
  `adapters/webhook.py` and mounts `POST /api/adapters/webhook`.
  Every request must carry an `X-Horus-Signature: sha256=<hex>`
  header validated against `HORUS_OS_WEBHOOK_SECRET` via
  `hmac.compare_digest`. The adapter refuses to run when the secret
  is unset. The handler routes the payload to one `run_agent` turn
  against an optional named profile, records a trace row, and
  returns the trace id with the final text.

## Storage shape

SQLite, single file, WAL mode, 5000ms busy timeout. Schema is
idempotent and re-applies safely on every boot. The current schema
version is 4 (v0.1 shipped v2).

Three tables matter for v0.2:

- `traces`: one row per provider iteration. Captures provider name,
  model, prompt, completion, tool calls, latency, error if any, plus
  `parent_trace_id` and `agent_profile_name` for delegated runs (v4).
- `note_writes`: one row per write to the markdown notes folder.
  Captures source agent run, target path, write mode (create or
  append), payload, and a hash for de-duplication.
- `agent_profiles`: one row per named profile. Captures `name`,
  `system_prompt`, `default_model`, `allowed_tools` (JSON list or
  null), `memory_scope`, `created_at`, `updated_at`. A `default`
  profile is bootstrapped on `init()` (v3).

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
6. **Adapters do not fork the core.** Third-party adapters declare an
   entry point. The core never needs to learn about them at build
   time, and a broken adapter cannot break the core dashboard.

## What is not in v0.2

- **Vector search.** Notes search is keyword-based. A vector store is
  on the v0.3+ list.
- **Authentication on the dashboard.** Bind to `127.0.0.1` only.
- **Retry, rate-limit handling, cost tracking.** Deferred to the v0.4
  observability milestone.
- **In-stream tool dispatch.** `run_agent_stream` surfaces tool
  requests as events; it does not execute them. Callers that need
  tool execution use `run_agent_loop`.
- **Discord, Slack, calendar, email adapters.** Reserved for the v0.3
  adapter ecosystem; only the reference HTTP webhook ships in v0.2.
- **Replay protection on the webhook adapter.** A signed request stays
  valid until the secret rotates. A timestamp plus nonce sliding
  window is a candidate for a future revision.
- **Profile editing in the dashboard.** The Agents tab is read-only;
  CRUD stays on the CLI and JSON API.
- **Provider-per-profile.** A sub-agent inherits the coordinator's
  provider. Mixing Anthropic and Gemini in one delegation tree is on
  the v0.3 list.

See `ROADMAP.md` for what is planned next.
