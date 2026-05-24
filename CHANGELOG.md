# Changelog

All notable changes to horus-os are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Python 3.13 added to the CI matrix (`lint-and-test` and `install-smoke` jobs) and to the package classifiers.

### Changed

## [0.3.0] - 2026-05-24

Third alpha. Takes the v0.2 adapter plugin interface from "one
reference webhook" to a real ecosystem: four first-class adapters
(Discord, Slack, Email, Calendar) on top of new lifecycle hooks
(`start`/`stop`) and an adapter registry surfaced through both a JSON
API and a Dashboard Adapters tab. Calendar is the first
tool-providing adapter, registering `list_calendar_events_today` and
the write-gated `create_calendar_event` onto a master
`ToolRegistry` that adapters now share via `AdapterContext`.

See `docs/MIGRATION-v0.2-to-v0.3.md` for upgrade notes from v0.2.

### Added

- **LifecycleAdapter Protocol** (`horus_os.LifecycleAdapter`).
  Optional `runtime_checkable` sibling Protocol with async
  `start(context)` and `stop()` hooks. Long-running adapters
  implement it alongside `Adapter` and get tied into the
  FastAPI app lifespan automatically.
- **AdapterRegistry + AdapterEntry** (`horus_os.AdapterEntry`,
  `horus_os.AdapterRegistry`). Per-app status tracker attached
  to `app.state.adapter_registry`. Tracks `name`, `status`,
  `last_activity_at`, `error_count`, `error_message`. Adapters
  mutate via `mark_running`, `mark_stopped`, `mark_error`,
  `touch`. Three status constants exported:
  `ADAPTER_STATUS_RUNNING`, `ADAPTER_STATUS_STOPPED`,
  `ADAPTER_STATUS_ERROR`.
- **AdapterContext additions** (`AdapterContext.registry`,
  `AdapterContext.tool_registry`). Both additive with safe
  defaults (default factory `AdapterRegistry` and `None`
  respectively), so v0.2 `AdapterContext(config=, data_dir=)`
  calls keep working.
- **`GET /api/adapters`** route. Returns one JSON object per
  discovered adapter with `name`, `status`, `last_activity_at`,
  `error_count`, `error_message`, and `supports_toggle`.
- **FastAPI lifespan integration.** `create_app` registers a
  lifespan that calls `await adapter.start(context)` at startup
  and `await adapter.stop()` at shutdown for every adapter with
  the matching hook. Errors are captured into the registry and
  isolated from sibling adapters.
- **DiscordAdapter** + new `[discord]` optional extra
  (`discord.py>=2.3`) + new `horus_os.adapters:discord` entry
  point. Connects to the Discord gateway, handles app mentions
  in guild channels and DMs, chunked replies to honor Discord's
  2000-char limit.
- **SlackAdapter** + new `[slack]` optional extra
  (`slack-sdk>=3.27`) + new `horus_os.adapters:slack` entry
  point. Mounts `POST /api/adapters/slack/events` and
  `POST /api/adapters/slack/commands`, verifies HMAC-SHA256
  signatures over `v0:{timestamp}:{body}` with a 300s replay
  window, routes `app_mention` and DM `message` events through
  `run_agent`.
- **EmailAdapter** (stdlib only) + new
  `horus_os.adapters:email` entry point. IMAP poll loop, SMTP
  reply with full RFC 5322 threading (`In-Reply-To`,
  `References`, `Message-ID`, `Date`). Poison-message safety:
  `\Seen` is set even on agent failure so a crashing message
  cannot loop forever.
- **CalendarAdapter** + new `[calendar]` optional extra
  (`google-api-python-client>=2.110`,
  `google-auth-oauthlib>=1.2`) + new `horus_os.adapters:calendar`
  entry point. First tool-providing adapter: registers
  `list_calendar_events_today` (always) and
  `create_calendar_event` (gated on
  `HORUS_OS_CALENDAR_WRITE_ALLOWED=true`) onto
  `AdapterContext.tool_registry`.
- **POST /api/adapters/{name}/enable** and
  **POST /api/adapters/{name}/disable** toggle routes. Drive
  `await adapter.start(context)` / `await adapter.stop()` on
  lifecycle adapters. 404 unknown, 400 missing hook, 500 on
  hook exception with the registry capturing the error.
- **`supports_toggle` field on `/api/adapters` entries.** Derived
  from `hasattr(adapter, "start") and hasattr(adapter, "stop")`.
- **Dashboard Adapters tab.** Fifth nav tab in the local
  dashboard. Renders one row per adapter with a color-coded
  status pill (green running, gray stopped, red error),
  `last_activity_at`, `error_count`, truncated `error_message`,
  and a per-adapter Enable / Disable / n/a button driven by
  `supports_toggle`. Polls `GET /api/adapters` every five
  seconds.

### Changed

- `AdapterContext` gained two additive fields (`registry`,
  `tool_registry`) with safe defaults. v0.2 callers and v0.2
  third-party adapters remain byte-identical.
- `WebhookAdapter` now calls `context.registry.touch(name)`
  after each successful request so it shows up in the new
  Dashboard Adapters tab with a live `last_activity_at`.
- `create_app` now constructs a master `ToolRegistry`, passes it
  through `AdapterContext.tool_registry`, and exposes both
  `app.state.tool_registry` and `app.state.adapters` for
  downstream code to introspect.

### Documentation

- `ARCHITECTURE.md` refreshed for v0.3: new Adapter ecosystem
  section covering LifecycleAdapter, AdapterRegistry, the
  lifespan integration, `tool_registry`, the four shipped
  adapters, toggle routes, and the Dashboard Adapters tab.
  Module layout updated; the deferred list renamed to "What is
  not in v0.3" with the shipped items removed and the new v0.3-era
  items (Socket Mode, OAuth CLI, write-tool merge into chat,
  soft-disable middleware) added.
- Four runnable, offline adapter examples added under
  `examples/`: `discord_adapter.py`, `slack_adapter.py`,
  `email_adapter.py`, `calendar_adapter.py`. Each uses the
  same `sys.modules` injection pattern the adapter tests use,
  runs without the optional SDK installed, and prints the
  dispatch and registry state.
- `docs/MIGRATION-v0.2-to-v0.3.md` added: additive Protocol
  changes, full env-var list, new optional dependency groups,
  no-schema-migration note, upgrade code samples.
- Four per-adapter setup guides under `docs/adapters/`:
  `DISCORD.md`, `SLACK.md`, `EMAIL.md`, `CALENDAR.md`.
- README updated with a "What is new in v0.3" section and
  Documents entries for the migration guide and the adapter
  setup guides.

## [0.1.0] - 2026-05-23

First alpha release. A working v0.1 foundation: install the package,
run an agent through CLI or local web chat, and read or write a
markdown notes folder with a full SQLite audit trail.

### Added

- **Agent runtime** (`run_agent`, `run_agent_async`, `run_agent_loop`)
  with sync and async paths. Multi-turn tool-execution loop.
- **Anthropic provider** with sync and async call functions and a
  `Conversation` class for stateful multi-turn use.
- **Google Gemini provider** with the same surface as Anthropic.
- **Tool registry** (`ToolRegistry`, `execute_tool_uses`) plus a
  built-in `read_file_tool` factory with optional path sandboxing.
- **Memory layer** for markdown notes folders: `NotesStore`,
  `list_notes` / `search_notes` / `read_note` / `create_note` /
  `append_note` tool factories.
- **SQLite persistence** (`Database`, `TraceRecord`, `NoteWrite`)
  with WAL mode, schema v2, idempotent migrations, and a
  reviewable audit trail for every note write.
- **CLI surface**: `horus-os init`, `init --interactive` (setup
  wizard with API key onboarding and 1-token live validation),
  `traces`, `run "<prompt>"`, `serve`.
- **Local web dashboard** served by FastAPI: chat surface, traces
  explorer, writes audit view. Single-file HTML + vanilla JS, no
  build step required.
- **JSON API** under `/api`: health, traces, trace-by-id, writes,
  chat.
- **Three-OS install verification** via GitHub Actions
  `install-smoke` job on (Ubuntu, macOS, Windows) by (Python 3.11,
  3.12).
- 175 automated tests covering every public API surface.
- Optional dependency groups: `[anthropic]`, `[gemini]`,
  `[dashboard]`, `[all]`, `[dev]`.

### Documentation

- `README.md`, `PROJECT.md`, `ARCHITECTURE.md`, `ROADMAP.md`,
  `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CLAUDE.md`.
- Apache 2.0 license.

### Known limitations

- No streaming responses. The dashboard waits for the full loop to
  finish before rendering.
- No retry, no rate-limit handling, no cost tracking. Defer to
  v0.5 Observability.
- The dashboard is a single-page vanilla-JS surface. A Next.js
  evolution is anticipated when the UX requirements grow.
- Tool execution loop bails out at 10 iterations by default; users
  can override with `--max-iterations`.

## [0.2.0] - 2026-05-23

Second alpha. Moves from "one agent answers questions" to "a personal
team of agents that can hand off to each other, with live streaming
responses in the CLI and dashboard." Named agent profiles persist in
SQLite. A coordinator delegates to sub-agents. Both providers stream
incremental tokens. An adapter plugin interface opens the door to
external surfaces.

See `docs/MIGRATION-v0.1-to-v0.2.md` for upgrade notes from v0.1.

### Added

- **Agent profiles.** `AgentProfile` dataclass plus a new
  `agent_profiles` table with `Database.load_profile`,
  `save_profile`, `list_profiles`, and `delete_profile`. A `default`
  profile is bootstrapped on every `init()` so a fresh database
  always has at least one row.
- **Multi-agent runtime.** `delegate_to_agent` tool produced by
  `make_delegate_tool(db, master_registry, parent_trace_id, budget,
  provider)`. Sub-agent runs inherit a shared `IterationBudget` so
  the iteration cap applies across the whole delegation tree.
  Parallel `delegate_to_agent` calls in a single coordinator turn
  execute concurrently and merge results back by `tool_use_id`.
- **Parent and child traces.** `TraceRecord` carries
  `parent_trace_id` and `agent_profile_name`; `Database.record_trace`
  accepts them as optional kwargs; `Database.list_child_traces`
  returns the children of a coordinator trace.
- **Streaming runtime.** `run_agent_stream(prompt, *, provider,
  model, max_tokens, system)` async generator that yields token
  strings and `ToolCallEvent` values. Both Anthropic and Gemini
  provider streaming paths land via `stream_anthropic_async` and
  `stream_gemini_async`.
- **CLI multi-agent surface.** `horus-os agents` group with `list`,
  `show`, `create`, `edit`, `delete`. `horus-os run --agent <name>`
  loads a profile and threads its `system_prompt` and
  `default_model` through the run.
- **Dashboard v0.2.** A new Agents tab, live SSE token streaming in
  the chat surface, and a delegate-tree expander on traces that
  carry an `agent_profile_name`. New server routes: `/api/agents`
  (list/show/create/edit/delete with `last_activity_at`),
  `/api/traces/{id}/children`, and `POST /api/chat/stream` with a
  `type`-discriminated SSE frame shape (`token`, `tool_call`,
  `done`, `error`).
- **Adapter contract.** `horus_os.adapters` package exposes the
  `Adapter` Protocol, `AdapterContext`, `discover_adapters`, and the
  `ADAPTER_ENTRY_POINT_GROUP` constant. Adapters are discovered via
  `entry_points(group="horus_os.adapters")` and bound onto FastAPI
  at `create_app` startup. Per-entry failures are isolated.
- **Reference adapter.** `WebhookAdapter` mounts
  `POST /api/adapters/webhook` with HMAC-SHA256 signature
  validation. Refuses to run when `HORUS_OS_WEBHOOK_SECRET` is
  unset.

### Changed

- `horus-os run "<prompt>"` now streams tokens to stdout by default.
  Pass `--no-stream` to restore the v0.1 buffered output.
  `ToolCallEvent` values surface on stderr as
  `[tool-request] {name}({input})`.
- SQLite schema upgraded automatically to version 4 on first
  startup. The migration is idempotent: v0.1 databases pick up the
  `agent_profiles` table (v3) and the `parent_trace_id` plus
  `agent_profile_name` columns on `traces` (v4) without manual
  intervention. v0.1 trace rows remain readable.

### Documentation

- `CONTRIBUTING.md` rewritten with dev setup, branch and commit
  conventions, code style, and contributor onboarding guidance now
  that v0.1 has shipped.
- `SECURITY.md` added with a private-disclosure process via GitHub
  Security Advisories.
- `ARCHITECTURE.md` refreshed for v0.2: multi-agent shape, streaming
  surface, adapter interface, schema v4, refreshed deferred list.
- `docs/MIGRATION-v0.1-to-v0.2.md` added with API additions, schema
  migration, behavior changes, and upgrade code samples.
- `examples/` added: `multi_agent.py`, `streaming.py`,
  `custom_adapter.py` plus an index README. All three run offline.
- GitHub issue templates (bug report, feature request) and pull
  request template added under `.github/`.

