# Roadmap

Planning detail lives under `.planning/`. Start with
`.planning/README.md` if you are new to the layout.

## Status at a glance

| Milestone | Phases | State | Tag |
|-----------|--------|-------|-----|
| v0.1 Foundation | 01-11 | shipped 2026-05-23 | `v0.1.0` |
| v0.2 Multi-Agent + Streaming | 12-21 | shipped 2026-05-23 | `v0.2.0` |
| v0.3 Adapter Ecosystem | 22-31 | shipped 2026-05-24 | `v0.3.0` |
| v0.4 Observability | 32-39 | shipped 2026-05-26 | `v0.4.0` |
| v0.5 Plugin System | 40-50 | shipped 2026-05-27 | `v0.5.0` |
| v0.6 Contribution Gate | 51-59 | folded in, never tagged | (none) |
| v0.7 Command Center | 60-68 | shipped 2026-06-03 | `v0.7.0` |
| v0.8 Local-first + Autonomous Research | 69-76 | shipped 2026-06-03 | `v0.8.0` |
| v0.9 Autonomy and Control | TBD | planned | |

For the live phase pointer read `.planning/STATE.md`. For the public status page read `STATUS.md`. For release contents read `CHANGELOG.md`.

## Where we are now

v0.8 is the latest tagged release (`v0.8.0`, 2026-06-03, SQLite schema v13). v0.1 through v0.8 have all shipped. v0.6 (Contribution Gate) was folded into the contribution-readiness work and never tagged on its own, so `v0.7.0` follows `v0.5.0` directly in the tag history.

Since the v0.8.0 tag, several product surfaces have landed on `main` and currently sit unreleased in the changelog `[Unreleased]` section. They ship in the next tagged cut:

- A streaming chat surface in the dashboard.
- An agent store with featured bundles and a no-code custom-agent builder.
- An optional Twilio voice and reservations adapter behind the `[voice]` extra.
- A 10-step onboarding tour with a visible spotlight across the dashboard.
- A mobile sidebar drawer and an agent Standup view.

## Next milestone: v0.9 Autonomy and Control

v0.8 shipped raw power: autonomous research, gated shell, and metered but unbounded spend. v0.9 lands the rails that make turning agents loose safe. Planned scope:

- An event and lifecycle-hook substrate plus priority execution lanes, the seam the rest registers onto.
- Monetary budget enforcement that pauses on breach, a daily pre-flight ceiling, and a stale-run reaper.
- Risk-tiered approvals, a destructive-action gate, and a verification gate.
- Safety hardening: secrets redaction, a subprocess resource guard, a skill threat scanner, and a loop detector.
- Watch rules and triggers on the event bus, with daily caps and dedup.
- Controlled autonomy: a spontaneous/idle loop and an overnight batch runner, behind every gate above.
- A minimal supervision surface: an approvals queue, a unified inbox, and a run-liveness watchdog.

v0.9 is planned, not yet committed to phases. It is the first of a six-milestone program (v0.9 through v0.14) that absorbs the full v0.9 gap analysis: v0.10 Memory and Learning, v0.11 Work Legibility, v0.12 Workspace and Models, v0.13 Interop and Distribution, and v0.14 Interaction Modality. The program-level map lives in `.planning/PROGRAM-v0.9-v0.14.md` and the underlying analysis in `.planning/research/v0.9-gap-analysis.md`; each milestone is finalized through the normal planning flow before any phase work begins.

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

## Shipped milestone summaries

For the deep per-phase breakdown of every shipped milestone (v0.1 through v0.8), read `.planning/ROADMAP.md`. For the public-facing shipped highlights, read `STATUS.md`. For what comes after v0.8, read the v0.9 section above and `.planning/PROGRAM-v0.9-v0.14.md`.

## Anti-goals

- Coupling to any single cloud provider beyond optional LLM API choice.
- Shipping features that require any paid account besides the user's LLM API key.
- Multi-tenant deployment patterns.
- A hosted SaaS offering of horus-os.
