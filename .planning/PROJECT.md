# horus-os

An open-source, self-hosted autonomous AI command center.

## What This Is

A personal AI command center that runs on the user's own machine. Multiple AI agents take instructions through a chat surface (CLI or web), execute tasks against a local persistent knowledge base, and surface results in a local web dashboard. Cloud AI calls are explicit, billed to the user's own API keys, and never required for the system to start.

## Core Value

Run a personal team of AI agents on your laptop, with full transparency over every action, every memory write, and every credential used.

## Requirements

### Active

Defined in REQUIREMENTS.md under `## v0.4 Observability` (METRIC, STORE, OTEL, DASH-4, PRICE, USAGE, plus continuation TEST/REL/MIG categories).

### Validated

- v0.1 Foundation: CORE, AGENT, TOOL, MEM, DASH, WIZARD, TEST-01..03, REL-01..02 (shipped 2026-05-23, tag `v0.1.0`).
- v0.2 Multi-Agent + Streaming: MA, STREAM, ADAPT, MIG, TEST-04..06, REL-03..04 (shipped 2026-05-23, tag `v0.2.0`).
- v0.3 Adapter Ecosystem: ART, DISC, SLAK, MAIL, CAL, DASH-3, TEST-07..10, REL-05..06 (shipped 2026-05-24, tag `v0.3.0`).

## Current Milestone: v0.4 Observability

**Goal:** Make every agent run, tool call, and LLM request observable — what it cost, how long it took, how often it failed — with a local-first dashboard and an opt-in OpenTelemetry exporter for users who already run their own observability stack.

**Target features:**
- Cost tracking — token usage and USD cost per agent, per model, per tool. Bundled, user-overridable `pricing.json`.
- Latency — end-to-end agent-run, per-LLM-call, and per-tool-call durations with p50/p95 surfaced in the dashboard.
- Tool reliability — success and error rates per tool, with last-error preview.
- Observability dashboard tab — new `/observability` view (cost-by-agent, latency p50/p95, error rate) plus extended numbers in the existing `/agents` tab.
- OpenTelemetry exporter — opt-in adapter (v0.3 adapter lifecycle pattern) behind an `otel` extra; emits OTLP traces to whatever backend the user already runs.
- `horus-os usage` CLI subcommand — JSON / CSV / table export over a window (e.g. `--since 7d`).
- Additive v3→v4 SQLite schema migration; v0.3 databases continue to read.

**Decisions locked in for v0.4:**
- Cost source: bundled `pricing.json` refreshed each release, user-overridable via config.
- OTel ships as a normal v0.3-style adapter (opt-in extra, lifecycle hooks), not a separate plugin system. v0.5 introduces the plugin manifest.
- Local-first: SQLite remains the source of truth. OTel export is additive.
- Anti-goal still in force: no paid third-party account required.
- Apache 2.0 license (unchanged).
- Three-OS hard gate before release (macOS, Ubuntu, Windows), Python 3.11 + 3.12.

**Shipped:**
- v0.1 Foundation — CLI + web chat, Anthropic + Gemini, one agent, six tools, memory layer (2026-05-23, tag `v0.1.0`).
- v0.2 Multi-Agent + Streaming — named agent profiles, `delegate_to_agent`, provider streaming, adapter plugin contract (2026-05-23, tag `v0.2.0`).
- v0.3 Adapter Ecosystem — lifecycle hooks, Discord/Slack/Email/Calendar adapters, AdapterRegistry, dashboard Adapters tab (2026-05-24, tag `v0.3.0`).

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
- Plugin manifest / third-party plugin distribution (deferred to v0.5).

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

*Last updated: 2026-05-24 — milestone v0.4 Observability started.*
