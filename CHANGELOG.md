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

### Documentation

- `CONTRIBUTING.md` rewritten with dev setup, branch and commit
  conventions, code style, and contributor onboarding guidance now
  that v0.1 has shipped.
- `SECURITY.md` added with a private-disclosure process via GitHub
  Security Advisories.
- `ARCHITECTURE.md` replaced its placeholder with the actual shape
  shipped in v0.1.0: module layout, data flow, storage shape,
  configuration model.
- GitHub issue templates (bug report, feature request) and pull
  request template added under `.github/`.

See `ROADMAP.md` for the v0.2 working list (multi-agent, web chat
streaming, adapter ecosystem).
