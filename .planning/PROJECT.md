# horus-os

An open-source, self-hosted autonomous AI command center.

## What This Is

A personal AI command center that runs on the user's own machine. Multiple AI agents take instructions through a chat surface (CLI or web), execute tasks against a local persistent knowledge base, and surface results in a local web dashboard. Cloud AI calls are explicit, billed to the user's own API keys, and never required for the system to start.

## Core Value

Run a personal team of AI agents on your laptop, with full transparency over every action, every memory write, and every credential used.

## Requirements

### Active

Defined in REQUIREMENTS.md under `## v0.5 Plugin System` (PLUG, MANIFEST, ISOLATE, DIST, plus continuation TEST/REL/MIG categories).

### Validated

- v0.1 Foundation: CORE, AGENT, TOOL, MEM, DASH, WIZARD, TEST-01..03, REL-01..02 (shipped 2026-05-23, tag `v0.1.0`).
- v0.2 Multi-Agent + Streaming: MA, STREAM, ADAPT, MIG, TEST-04..06, REL-03..04 (shipped 2026-05-23, tag `v0.2.0`).
- v0.3 Adapter Ecosystem: ART, DISC, SLAK, MAIL, CAL, DASH-3, TEST-07..10, REL-05..06 (shipped 2026-05-24, tag `v0.3.0`).
- v0.4 Observability: METRIC, STORE, PRICE, DASH-4, USAGE, OTEL, BASELINE, TEST-11..15, REL-07..09, MIG-04 (shipped 2026-05-26, tag `v0.4.0`).

## Current Milestone: v0.5 Plugin System

**Goal:** Turn horus-os from "built-in adapters and tools only" into "anyone can ship a horus-os plugin." A plugin manifest contract, an installer flow, a runtime that loads third-party tools and adapters from a manifest with bounded permissions, and a dashboard surface for inspecting / enabling / disabling installed plugins.

**Target features:**
- Plugin manifest schema — versioned `horus-plugin.toml` (or JSON) declaring name, version, entry points, declared tools and adapters, capabilities/permissions requested, compatible horus-os range.
- Discovery and loading — discover plugins via Python entry points group (`horus_os.plugins`) plus an explicit `~/.horus-os/plugins/` directory; load through the same Tool registry and AdapterRegistry contracts shipped in v0.1/v0.2.
- Permission model — declared capabilities (e.g. `filesystem.read`, `net.outbound`, `secrets.read`) with a default-deny posture; user grants explicit on first run; revocable from dashboard.
- Installer flow — `horus-os plugins install <pip-spec>` (and `uninstall`, `list`, `info`) that wraps `pip install` into the active venv, validates manifest, and surfaces requested capabilities before the user confirms.
- Dashboard plugins tab — list installed plugins, their declared tools/adapters, granted capabilities, lifecycle status, and last error. Toggle enable/disable per plugin.
- Failure isolation — a broken plugin must not crash horus-os; load failures, runtime errors, and slow start/stop hooks degrade to "plugin error" status with telemetry rolling into the v0.4 observability surface (latency, error rate per plugin).
- Reference plugin — one published example plugin (`horus-os-example-plugin`) shipped as a separate package on the same repo, serving as the contract reference for third-party authors.
- Additive v4→v5 SQLite schema migration; v0.4 databases continue to read.

**Decisions to confirm during planning:**
- Manifest format: TOML preferred (consistent with `pyproject.toml`; ships in stdlib via `tomllib` on Python 3.11+). To be locked at requirements time.
- Discovery: Python entry points first (works for `pip install`-ed plugins), explicit local directory second (works for unpublished dev plugins). No HTTP catalog in v0.5.
- Permission grants: persisted in SQLite; user-visible in dashboard; never silently re-granted across plugin upgrades that change the requested set.
- Anti-goal still in force: no paid third-party account required.
- Apache 2.0 license (unchanged).
- Three-OS hard gate before release (macOS, Ubuntu, Windows), Python 3.11 + 3.12.

**Shipped:**
- v0.1 Foundation — CLI + web chat, Anthropic + Gemini, one agent, six tools, memory layer (2026-05-23, tag `v0.1.0`).
- v0.2 Multi-Agent + Streaming — named agent profiles, `delegate_to_agent`, provider streaming, adapter plugin contract (2026-05-23, tag `v0.2.0`).
- v0.3 Adapter Ecosystem — lifecycle hooks, Discord/Slack/Email/Calendar adapters, AdapterRegistry, dashboard Adapters tab (2026-05-24, tag `v0.3.0`).
- v0.4 Observability — ObservationBus, SQLite cost/latency/reliability persistence, bundled pricing.json, `/observability` dashboard tab, `horus-os usage` CLI, opt-in OTel adapter behind `[otel]` extra (2026-05-26, tag `v0.4.0`).

See `.planning/ROADMAP.md` for full phase-level history.

## Context

**Anticipated architecture:**
- FastAPI server bound to localhost
- SQLite (WAL mode) as the only required persistence layer
- Local markdown notes folder as the human-readable knowledge surface
- Next.js dashboard served locally (optional, the CLI works without it)
- Direct Anthropic SDK and Google Gemini SDK calls, no provider abstraction

**Tech Stack (planned):**
- Backend: Python 3.11+, FastAPI, SQLite, aiosqlite
- Frontend: Next.js, React, Tailwind
- AI: Anthropic SDK, Google Gemini SDK
- CI: GitHub Actions on Ubuntu, macOS, Windows

## Key Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| Anthropic + Gemini, no abstraction layer | Both providers have first-class SDK support and well-documented APIs. An abstraction layer adds debt before the first user. | accepted (v0.1) |
| CLI and web chat parallel at v0.1 | Different users prefer different surfaces. Both share the same backend so the marginal cost is the second UI shell, not a second runtime. | accepted (v0.1) |
| SQLite over Postgres for default | Single file, zero ops, trivially portable, ships with the binary. Postgres is an option later for users who want it. | accepted (v0.1) |
| Apache 2.0 license | Permissive, patent-grant clause important for AI tooling. Compatible with most third-party libraries we will use. | accepted (v0.1) |

## Out of Scope (initial release)

- Hosted SaaS deployment.
- Mobile clients.
- Multi-tenant patterns.
- Kubernetes operators.
- Features that require any paid third-party account beyond user-supplied LLM API keys.
- Voice integrations (no current milestone).
- Hosted plugin marketplace / discovery catalog (post-v0.5; v0.5 uses Python entry points + local directory only).
- Sandboxed plugin execution via OS-level isolation (subprocess/container). v0.5 uses in-process loading with capability-declaration permission grants; OS isolation is a v0.6+ consideration if real-world abuse warrants it.

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

## Footer

*Last updated: 2026-05-26 — milestone v0.5 Plugin System started; v0.4 Observability shipped as v0.4.0.*
