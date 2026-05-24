# Architecture

This document describes the actual shape of `horus-os` on the `main`
branch heading into v0.3.0. For project intent and what is out of
scope, see `PROJECT.md`. For the v0.1 to v0.2 upgrade path, see
`docs/MIGRATION-v0.1-to-v0.2.md`. For the v0.2 to v0.3 upgrade path,
see `docs/MIGRATION-v0.2-to-v0.3.md`.

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
                |  Adapter + LifecycleAdapter|
                |  Protocols +               |
                |  entry-point discovery +   |
                |  AdapterRegistry +         |
                |  FastAPI lifespan          |
                |  WebhookAdapter (ref)      |
                |  DiscordAdapter            |
                |  SlackAdapter              |
                |  EmailAdapter              |
                |  CalendarAdapter (tools)   |
                +----------------------------+
```

Everything runs in a single process by default. The dashboard is
served by the same FastAPI app that powers the CLI's `serve`
subcommand. There is no separate frontend build; the dashboard is
single-page vanilla JS shipped as a package data file. Adapters are
mounted at app startup via `discover_adapters()` and bind their own
routes onto the FastAPI instance. Long-running adapters additionally
implement the optional `LifecycleAdapter` Protocol and get
`start`/`stop` hooks tied to the FastAPI app lifespan; their status
is queryable at `GET /api/adapters` and toggleable via
`POST /api/adapters/{name}/{enable,disable}`.

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
| `adapters/base.py` | `Adapter` Protocol, optional `LifecycleAdapter` Protocol (async `start`/`stop`), `AdapterContext` (with `registry` and optional `tool_registry`), `AdapterEntry`, `AdapterRegistry`, three `ADAPTER_STATUS_*` constants, `discover_adapters`, `ADAPTER_ENTRY_POINT_GROUP`. |
| `adapters/webhook.py` | Reference `WebhookAdapter`: HMAC-SHA256 signed HTTP webhook receiver mounted at `/api/adapters/webhook`. |
| `adapters/discord_adapter.py` | `DiscordAdapter` (v0.3). Lazy `discord.py` import, gateway mention/DM handler, chunked replies, lifecycle hooks. |
| `adapters/slack_adapter.py` | `SlackAdapter` (v0.3). Lazy `slack-sdk` import, Events API + slash commands, HMAC-SHA256 signed inbound webhook. |
| `adapters/email_adapter.py` | `EmailAdapter` (v0.3). Stdlib-only IMAP poll plus SMTP reply with RFC 5322 threading headers. |
| `adapters/calendar_adapter.py` | `CalendarAdapter` (v0.3). Lazy Google API import, registers `list_calendar_events_today` (always) and `create_calendar_event` (gated on `HORUS_OS_CALENDAR_WRITE_ALLOWED`) onto `context.tool_registry`. |
| `config.py` | Config file location, load, and save. Honors `HORUS_OS_HOME` for the data directory. |
| `types.py` | Shared dataclasses and type aliases: `Tool`, `ToolUse`, `ToolResult`, `ToolCallEvent`, `AgentResult`, `AgentProfile`, `NoteRef`, `NoteWrite`. |

`tests/` mirrors `src/horus_os/` one to one. Every public surface is
covered. The suite is at 437 passing tests heading into Phase 28.

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

## Adapter ecosystem

v0.3 expands the adapter contract into a small ecosystem: an
optional lifecycle Protocol, a per-app registry that tracks live
status, FastAPI lifespan integration, four shipped adapters, and
operator-facing toggle routes plus a Dashboard tab.

### LifecycleAdapter

A sibling `runtime_checkable` Protocol from `adapters/base.py`. An
adapter that needs to launch a long-running task (a gateway
socket, an IMAP poll loop, a scheduled tick) implements it
alongside the base `Adapter` Protocol:

```
class MyAdapter:
    name = "my_adapter"

    def bind(self, app, context): ...
    async def start(self, context): ...
    async def stop(self): ...
```

Runtime dispatch in the FastAPI lifespan uses `hasattr` rather
than `isinstance(adapter, LifecycleAdapter)`, so adapters that
implement only one of the two hooks still work. The Protocol is
exported for type hints and for the documentation it provides at
the call site.

### AdapterRegistry

`AdapterRegistry` is attached to `app.state.adapter_registry` at
`create_app` time. Each adapter discovered through entry points
gets a registered `AdapterEntry` row carrying `name`, `status`
(`running`, `stopped`, or `error`), `last_activity_at` (UTC
iso8601 string), `error_count`, and `error_message`. Adapters
mutate the row through narrow methods (`mark_running`,
`mark_stopped`, `mark_error`, `touch`) and read it back through
`get(name)` or `entries()`.

`GET /api/adapters` returns every entry as a JSON list. Each
object includes `name`, `status`, `last_activity_at`,
`error_count`, `error_message`, and `supports_toggle` (true when
the adapter implements both `start` and `stop`).

### FastAPI lifespan integration

`create_app` registers an async lifespan handler that, at
startup, calls `await adapter.start(context)` on every discovered
adapter that exposes a `start` coroutine. At shutdown the lifespan
walks the adapter list in reverse order and awaits `stop()` on
each one. Exceptions raised by hook calls are caught, logged into
the registry as `mark_error`, and do not propagate; one broken
adapter cannot block startup or shutdown of the others.

### AdapterContext.tool_registry

`AdapterContext` gained a second additive field in Phase 26:
`tool_registry: ToolRegistry | None`. Tool-providing adapters
(the Calendar adapter today) register agent-callable tools onto
it during `bind`. The field defaults to None so v0.2 callers and
older third-party adapters keep working byte-identical; the
Calendar adapter checks for None and surfaces a clear error via
the registry rather than raising. `create_app` (Phase 27) wires a
fresh `ToolRegistry` through every context and also exposes the
same instance as `app.state.tool_registry` for downstream code to
inspect.

### Shipped adapters at a glance

| Adapter | Transport | Lifecycle | Tools | Optional extra | Setup |
|---------|-----------|-----------|-------|----------------|-------|
| `discord` | Discord gateway (`discord.py`) | start + stop | none | `[discord]` | `docs/adapters/DISCORD.md` |
| `slack` | HTTP Events API + slash commands (`slack-sdk`) | bind only | none | `[slack]` | `docs/adapters/SLACK.md` |
| `email` | IMAP poll + SMTP reply (stdlib) | start + stop | none | none (stdlib) | `docs/adapters/EMAIL.md` |
| `calendar` | Google Calendar API (`google-api-python-client`) | bind only | `list_calendar_events_today`, optional `create_calendar_event` | `[calendar]` | `docs/adapters/CALENDAR.md` |

Every shipped adapter is opt-in. Each lazily imports its SDK
inside `start` or `bind` so the package imports cleanly when the
optional extra is not installed. Each declares its entry point in
`pyproject.toml` under `[project.entry-points."horus_os.adapters"]`
so `discover_adapters` finds it automatically after install.

### Toggle routes and Dashboard Adapters tab

Two toggle routes operate on lifecycle adapters:

- `POST /api/adapters/{name}/disable` awaits `adapter.stop()` and
  flips the registry entry to `stopped`. 404 on unknown name, 400
  when the adapter has no `stop` hook, 500 with `mark_error` on
  hook exception.
- `POST /api/adapters/{name}/enable` awaits `adapter.start(context)`
  and flips the registry entry to `running`. Same error semantics.

The Dashboard's Adapters tab polls `GET /api/adapters` every five
seconds and renders one row per adapter with a color-coded status
pill (green running, gray stopped, red error), the last activity
timestamp, error count, the most recent error message, and a
per-adapter Enable / Disable / n/a button driven by
`supports_toggle`.

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

## What is not in v0.3

- **Vector search.** Notes search is keyword-based. A vector store
  remains on the post-v0.3 list.
- **Authentication on the dashboard.** Bind to `127.0.0.1` only.
- **Retry, rate-limit handling, cost tracking.** Deferred to the
  v0.4 observability milestone.
- **In-stream tool dispatch.** `run_agent_stream` surfaces tool
  requests as events; it does not execute them. Callers that need
  tool execution use `run_agent_loop`.
- **Replay protection on the webhook adapter.** A signed request
  stays valid until the secret rotates. A timestamp plus nonce
  sliding window is a candidate for a future revision.
- **Profile editing in the dashboard.** The Agents tab is
  read-only; CRUD stays on the CLI and JSON API.
- **Provider-per-profile.** A sub-agent inherits the coordinator's
  provider. Mixing Anthropic and Gemini in one delegation tree is
  on the post-v0.3 list.
- **Socket Mode for Slack.** The Slack adapter ships with the
  HTTP Events API path only. Socket Mode (over a WebSocket) is a
  future option for operators behind NAT.
- **OAuth CLI for Calendar.** The one-time OAuth bootstrap that
  produces `calendar-token.json` is documented in
  `docs/adapters/CALENDAR.md` but not yet wrapped as a
  `horus-os calendar oauth` subcommand.
- **Write-tool merge into the chat path.** Tools registered by
  adapters (Calendar today) land on `app.state.tool_registry`.
  Merging that registry into `/api/chat` so the dashboard agent
  picks up adapter-provided tools out of the box is a follow-up.
- **Soft-disable middleware for bind-only adapters.** Toggle
  routes operate on lifecycle adapters today; bind-only adapters
  (Slack, Calendar) show `supports_toggle: false` and require a
  process restart to remove their routes.

See `ROADMAP.md` for what is planned next.
