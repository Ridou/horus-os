# Changelog

All notable changes to horus-os are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

## [Unreleased]

Heading into v0.2.0. Phase 21 will replace this section with a
`[0.2.0] - YYYY-MM-DD` heading and tag the release.

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

See `ROADMAP.md` for the rest of the v0.2 work (test surface
expansion, three-OS install verification, v0.2.0 release).
