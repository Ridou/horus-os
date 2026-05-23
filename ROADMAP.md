# Roadmap

Planning detail lives under `.planning/`. Start with
`.planning/README.md` if you are new to the layout.

## Status at a glance

| Milestone | Phases | State | Tag |
|-----------|--------|-------|-----|
| v0.1 Foundation | 01-11 | shipped 2026-05-23 | `v0.1.0` |
| v0.2 Multi-Agent + Streaming | 12-21 | shipped 2026-05-23 | `v0.2.0` |
| **v0.3 Adapter Ecosystem** | **22-31** | **active** | `v0.3.0` (planned) |
| v0.4 Observability | TBD | not planned | |
| v0.5 Plugin system | TBD | not planned | |

## Active milestone: v0.3 Adapter Ecosystem

**Goal:** Take the v0.2 adapter plugin interface from "one reference webhook" to a real ecosystem. Ship four first-class adapters (Discord, Slack, email, calendar) that turn horus-os into a personal command center reachable from the user's existing channels. Add adapter lifecycle hooks for long-running connections, surface adapter health in the dashboard, and document the setup path for each integration.

### Decisions locked in for v0.3

| Decision | Choice |
|----------|--------|
| Lifecycle hooks | Adapter Protocol gains optional `start(ctx)` and `stop()` async hooks. FastAPI lifespan integration runs them at startup and shutdown. Existing webhook adapter works unchanged. |
| Adapters shipped | Discord, Slack, email (IMAP+SMTP), calendar (Google). Each ships with mocked-SDK tests and a setup guide. |
| Adapter SDKs | Discord and Slack via official Python SDKs (added as optional deps under their adapter's extra). Email via stdlib `imaplib` + `smtplib`. Calendar via `google-api-python-client`. |
| Auth and secrets | Each adapter reads its credentials from an env var; calendar uses OAuth with token storage in the data dir. |
| Dashboard | New `/adapters` view shows status (running, stopped, error), last activity, error count. Enable/disable via REST. |
| License | Apache 2.0 (unchanged) |
| Three-OS gate | Same hard gate as v0.1 (Phase 10) and v0.2 (Phase 20), re-applied before release. |

### Phases

| # | Title | Goal | Status |
|---|-------|------|--------|
| 22 | Adapter lifecycle hooks | Optional `start(ctx)`/`stop()` on Adapter Protocol; FastAPI lifespan integration; `/api/adapters` reports status. | queued |
| 23 | Discord adapter | Bot listens for mentions/DMs, routes to a configured agent, replies in channel. Setup guide for token + intents. | queued |
| 24 | Slack adapter | Events API for `app_mention` and DMs; signing-secret HMAC verification; slash command support. | queued |
| 25 | Email adapter | IMAP poll + SMTP send. Thread-preserving replies. Stdlib only. | queued |
| 26 | Calendar adapter | Google Calendar "list today's events" tool; optional event creation gated behind a permission flag. | queued |
| 27 | Dashboard adapter management | `/adapters` view with status, last activity, error count; enable/disable from UI. | queued |
| 28 | Documentation and examples refresh | ARCHITECTURE update; four adapter examples; v0.2-to-v0.3 migration guide. | queued |
| 29 | Test surface expansion | Lifecycle tests, mocked-SDK tests per adapter, cross-adapter routing. | queued |
| 30 | Three-OS install verification (v0.3) | install-smoke green on Ubuntu/macOS/Windows for Python 3.11 + 3.12. | queued |
| 31 | v0.3.0 release | Tag v0.3.0, CHANGELOG updated, version bumped, GitHub Release with migration notes. | queued |

**Parallelization:** `22 → (23 ∥ 24 ∥ 25 ∥ 26) → 27 → 28 → 29 → 30 → 31`. Phase 22 (lifecycle hooks) gates the four adapter implementations because long-running adapters need start/stop semantics that the v0.2 Protocol does not provide. After 22 lands, the four adapters can ship in parallel.

## Shipped: v0.2 Multi-Agent + Streaming

**Goal (shipped):** Move from "one agent answers questions" to "a personal team of agents that can hand off to each other, with live streaming responses in the CLI and dashboard."

### Decisions locked in for v0.2

| Decision | Choice |
|----------|--------|
| Multi-agent shape | Named agent profiles in SQLite. A coordinator can delegate to sub-agents via the `delegate_to_agent` tool. Parent/child links in the trace table. |
| Streaming | Provider streaming APIs (Anthropic stream, Gemini stream) via a new `run_agent_stream` async generator. `run_agent` keeps its v0.1 surface for non-streaming callers. |
| Adapter ecosystem | Plugin contract defined via `importlib.metadata.entry_points("horus_os.adapters")`. One reference adapter (HTTP webhook). Discord/Slack adapters in v0.3. |
| Migration | v0.1 SQLite databases upgrade to v0.2 schema idempotently. v0.1 traces remain readable. Downgrade is one-way and documented. |
| License | Apache 2.0 (unchanged) |
| Three-OS gate | Same hard gate as v0.1 (Phase 10) re-applied before release. |

### Phases (all shipped 2026-05-23)

| # | Title | Goal |
|---|-------|------|
| 12 | Agent profile model and schema migration | `agent_profiles` table, idempotent v2->v3 migration, default agent bootstrap |
| 13 | Multi-agent orchestration runtime | `delegate_to_agent` tool, shared iteration budget, parent/child traces |
| 14 | Streaming response support | `run_agent_stream` + provider streaming + `ToolCallEvent` |
| 15 | CLI multi-agent surface | `horus-os agents` subcommand, `run --agent`, streaming by default |
| 16 | Dashboard multi-agent view and streaming chat | `/agents` view, SSE chat, delegate-tree expander |
| 17 | Adapter plugin interface | Adapter Protocol, entry-point discovery, HMAC webhook reference adapter |
| 18 | Documentation and examples refresh | ARCHITECTURE v0.2 refresh, three examples, v0.1-to-v0.2 migration guide |
| 19 | Test surface expansion | Cross-phase E2E coverage, streaming partial-failure, adapter round-trip |
| 20 | Three-OS install verification (v0.2) | install-smoke green on Ubuntu, macOS, Windows for Python 3.11 + 3.12 |
| 21 | v0.2.0 release | v0.2.0 tagged, CHANGELOG rotated, GitHub Release published |

## Shipped: v0.1 Foundation

**Goal (shipped):** Smallest standalone system a stranger can clone, configure with their own API keys, and use through either a CLI or a local web chat. One agent. One tool. One persistent memory layer. Two LLM providers (Anthropic, Google Gemini) wired in directly.

### Decisions locked in for v0.1

| Decision | Choice |
|----------|--------|
| Chat surfaces | CLI and web chat both shipped at v0.1, in parallel |
| LLM providers | Anthropic and Google Gemini both, direct SDKs, no abstraction layer |
| API key onboarding | Setup wizard provides direct links to the provider consoles plus a click-to-paste flow so users can be configured in under five minutes |
| Runtime target | macOS, Ubuntu 22.04, Windows 11 (three-OS hard gate before public release) |
| License | Apache 2.0 |

### Phases (all shipped 2026-05-23)

| # | Title | Goal |
|---|-------|------|
| 01 | Repo scaffold and CI | pyproject.toml, src layout, ruff + pytest, GitHub Actions on Ubuntu, macOS, Windows |
| 02 | Agent runtime core | Python module that takes a prompt, invokes Anthropic or Gemini with one tool, returns a structured result. Sync and async paths. |
| 03 | Persistence layer | SQLite schema for tasks, traces, agent state. Migrations idempotent. WAL mode. |
| 04 | Tool registry | Register a callable as a tool, expose it to the agent, log every invocation. First example tool: read a local file. |
| 05 | Memory layer, read path | Agent searches a markdown notes folder and reads files. |
| 06 | Memory layer, write path | Agent appends to the notes folder with a structured trail. Every write reviewable. |
| 07 | CLI surface | `horus-os run "<prompt>"`. Also `init`, `serve`, `traces`. Multi-turn tool-execution loop. |
| 08 | Web chat and dashboard | Single-page HTML dashboard served locally by FastAPI. Chat, traces, writes audit. |
| 09 | Setup wizard with API key onboarding | `horus-os init --interactive`. Direct links to provider consoles. Live-pings keys before saving. Idempotent and resumable. |
| 10 | Three-OS install verification | install-smoke CI on macOS, Ubuntu, Windows. |
| 11 | First public release | v0.1.0 tagged, CHANGELOG, GitHub Release. |

## Future milestones (placeholders)

- **v0.4 Observability.** Cost tracking per agent, per tool. Latency dashboards.
- **v0.5 Plugin system.** Third-party tools and agents load from a manifest.

Shape is decided in flight. Open an issue or discussion to push on any of these.

## Anti-goals

- Coupling to any single cloud provider beyond optional LLM API choice.
- Shipping features that require any paid account besides the user's LLM API key.
- Multi-tenant deployment patterns.
- A hosted SaaS offering of horus-os.
