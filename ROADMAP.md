# Roadmap

Planning detail lives under `.planning/`. Start with
`.planning/README.md` if you are new to the layout.

## Status at a glance

| Milestone | Phases | State | Tag |
|-----------|--------|-------|-----|
| v0.1 Foundation | 01-11 | shipped 2026-05-23 | `v0.1.0` |
| **v0.2 Multi-Agent + Streaming** | **12-21** | **active** | `v0.2.0` (planned) |
| v0.3 Adapter ecosystem | TBD | not planned | |
| v0.4 Observability | TBD | not planned | |
| v0.5 Plugin system | TBD | not planned | |

## Active milestone: v0.2 Multi-Agent + Streaming

**Goal:** Move from "one agent answers questions" to "a personal team of agents that can hand off to each other, with live streaming responses in the CLI and dashboard."

### Decisions locked in for v0.2

| Decision | Choice |
|----------|--------|
| Multi-agent shape | Named agent profiles in SQLite. A coordinator can delegate to sub-agents via the `delegate_to_agent` tool. Parent/child links in the trace table. |
| Streaming | Provider streaming APIs (Anthropic stream, Gemini stream) via a new `run_agent_stream` async generator. `run_agent` keeps its v0.1 surface for non-streaming callers. |
| Adapter ecosystem | Plugin contract defined via `importlib.metadata.entry_points("horus_os.adapters")`. One reference adapter (HTTP webhook). Discord/Slack adapters deferred to v0.3. |
| Migration | v0.1 SQLite databases upgrade to v0.2 schema idempotently. v0.1 traces remain readable. Downgrade is one-way and documented. |
| License | Apache 2.0 (unchanged) |
| Three-OS gate | Same hard gate as v0.1 (Phase 10) re-applied before release. |

### Phases

| # | Title | Goal | Status |
|---|-------|------|--------|
| 12 | Agent profile model and schema migration | `agent_profiles` table with name, system prompt, default model, allowed tools, memory scope. Idempotent forward migration from v0.1. At least one default agent auto-created on `init`. | queued |
| 13 | Multi-agent orchestration runtime | `delegate_to_agent` tool. Coordinator/sub-agent runtime. Parent/child trace links. Iteration bound applies to the whole tree. | queued |
| 14 | Streaming response support | `run_agent_stream` async generator. Anthropic and Gemini streaming SDK paths. Backwards-compatible with `run_agent`. | queued |
| 15 | CLI multi-agent surface | `horus-os agents` (list/show/create/edit/delete). `horus-os run --agent <name>`. Streaming output by default; `--no-stream` falls back. | queued |
| 16 | Dashboard multi-agent view and streaming chat | Agents list, per-agent activity, delegate-tree visualization per run, live token streaming in the chat surface. | queued |
| 17 | Adapter plugin interface | Plugin contract via `horus_os.adapters` entry point. One reference adapter: HTTP webhook receiver. Third-party adapters register without forking. | queued |
| 18 | Documentation and examples refresh | Update ARCHITECTURE.md for the multi-agent shape. Add `examples/multi_agent.py`, `examples/streaming.py`, `examples/custom_adapter.py`. Document the v0.1 to v0.2 migration. | queued |
| 19 | Test surface expansion | End-to-end multi-agent flows, streaming partial-failure modes, adapter contract tests. Three-OS coverage maintained. | queued |
| 20 | Three-OS install verification (v0.2) | Same hard gate as Phase 10, re-targeted at the v0.2 feature set. | queued |
| 21 | v0.2.0 release | Tag v0.2.0 on origin, CHANGELOG updated, version bumped, GitHub Release published with migration notes. | queued |

**Parallelization:** `12 → 13 → (14 ∥ 15 ∥ 16 ∥ 17) → 18 → 19 → 20 → 21`. Phase 12 gates everything because it changes storage. After Phase 13 lands the delegation runtime, surfaces and the adapter interface can ship in parallel.

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

- **v0.3 Adapter ecosystem.** Discord, Slack, calendar, email as opt-in integrations on top of the v0.2 plugin interface.
- **v0.4 Observability.** Cost tracking per agent, per tool. Latency dashboards.
- **v0.5 Plugin system.** Third-party tools and agents load from a manifest.

Shape is decided in flight. Open an issue or discussion to push on any of these.

## Anti-goals

- Coupling to any single cloud provider beyond optional LLM API choice.
- Shipping features that require any paid account besides the user's LLM API key.
- Multi-tenant deployment patterns.
- A hosted SaaS offering of horus-os.
