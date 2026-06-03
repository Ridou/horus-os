# horus-os

An open-source, self-hosted autonomous AI command center.

## What This Is

A personal AI command center that runs on the user's own machine. Multiple AI agents take instructions through a chat surface (CLI or web), execute tasks against a local persistent knowledge base, and surface results in a local web dashboard. Cloud AI calls are explicit, billed to the user's own API keys, and never required for the system to start.

## Core Value

Run a personal team of AI agents on your laptop, with full transparency over every action, every memory write, and every credential used.

## Requirements

### Active

Defined in REQUIREMENTS.md under `## v0.7 Command Center` (design-system, dashboard-pages, starter-team, seed-content, Discord-control-bot, Supabase/Vercel always-live, Tailscale/always-on, and the unified setup-verify and key-management categories).

### Validated

- v0.1 Foundation: CORE, AGENT, TOOL, MEM, DASH, WIZARD, TEST-01..03, REL-01..02 (shipped 2026-05-23, tag `v0.1.0`).
- v0.2 Multi-Agent + Streaming: MA, STREAM, ADAPT, MIG, TEST-04..06, REL-03..04 (shipped 2026-05-23, tag `v0.2.0`).
- v0.3 Adapter Ecosystem: ART, DISC, SLAK, MAIL, CAL, DASH-3, TEST-07..10, REL-05..06 (shipped 2026-05-24, tag `v0.3.0`).
- v0.4 Observability: METRIC, STORE, PRICE, DASH-4, USAGE, OTEL, BASELINE, TEST-11..15, REL-07..09, MIG-04 (shipped 2026-05-26, tag `v0.4.0`).
- v0.5 Plugin System: PLUG, MANIFEST, ISOLATE, INSTALL, PERMISSION, DASH-5, REFERENCE, TEST-16..21, REL-10..12, MIG-05 (shipped 2026-05-27, tag `v0.5.0`).

## Current Milestone: v0.7 Command Center

**Goal:** Turn the plain local dashboard into a polished command center, ship a named starter team, and make the full optional integration suite (Discord, Supabase, Vercel, Tailscale, GitHub, AI providers, and the existing adapters) connectable through guided in-dashboard walkthroughs with green-light verification and in-app key management. Every integration is optional, so local-only operation requires no SaaS.

**Target features:**
- Design system and frontend rebuild: Tailwind v4 tokens, Radix primitives, Lucide icons, Recharts, a new layout shell with sidebar navigation, dark theme.
- Tier-1 dashboard pages: /team and /team/[agent] (team-as-organization), /memory vault browser, /tasks, /activity, redesigned /traces and /costs, a real /settings, and /about.
- Starter team and seed content: five generic agents (Coordinator, Engineer, Researcher, Writer, Operator) with SOUL.md personas auto-created on init, an example vault, a demo trace, and a first-run onboarding tour.
- Discord control bot (opt-in, feature parity): idempotent non-destructive channel bootstrap, the "#horus type, open a thread, route to the orchestrator" flow, slash commands, outbound task-status cards, reaction feedback, and a configurable admin role. Never a required transport.
- Always-live mission control (opt-in): a SQLite to Supabase sync loop, Supabase-backed dashboard reads, schema migrations, a "deploy your own dashboard to Vercel" path, and a Vercel token used only to observe deploy status.
- Remote access and 24/7 operation (opt-in): Tailscale remote-access docs, a cross-platform always-on service install, and in-process cron routine schedulers, with a prominent caveat that /api has no auth layer before any public exposure.
- Unified Setup and Verify experience: an Integrations and Settings surface listing every connector with a status indicator, a per-integration guided popup walkthrough (modal plus stepper, portal deep-links, screenshots, the exact env var or command), a green-light "you have what you need" readiness check, and in-app key management to adjust or replace credentials.

**Key context:**
- All integrations are optional. No paid third-party account is required to run horus-os locally, preserving the core value and the no-required-SaaS anti-goal.
- In-app key editing is acceptable on the default 127.0.0.1 bind. Remote exposure (Tailscale Funnel or a Vercel-fronted dashboard) requires an authentication layer on /api first, and the walkthroughs flag this.
- This milestone deliberately reverses the v0.7-design-inspiration deferral of Vercel, Supabase, and an expanded Discord bot, kept safe by making all three opt-in.
- The private PR-review pipeline and the personal phone-geolocation sensor are excluded entirely.
- Apache 2.0 license (unchanged). Three-OS hard gate before release (macOS, Ubuntu, Windows), Python 3.11 and 3.12.

**Shipped:**
- v0.1 Foundation - CLI + web chat, Anthropic + Gemini, one agent, six tools, memory layer (2026-05-23, tag `v0.1.0`).
- v0.2 Multi-Agent + Streaming - named agent profiles, `delegate_to_agent`, provider streaming, adapter plugin contract (2026-05-23, tag `v0.2.0`).
- v0.3 Adapter Ecosystem - lifecycle hooks, Discord/Slack/Email/Calendar adapters, AdapterRegistry, dashboard Adapters tab (2026-05-24, tag `v0.3.0`).
- v0.4 Observability - ObservationBus, SQLite cost/latency/reliability persistence, bundled pricing.json, `/observability` dashboard tab, `horus-os usage` CLI, opt-in OTel adapter behind `[otel]` extra (2026-05-26, tag `v0.4.0`).
- v0.5 Plugin System - TOML manifest contract, entry-point + filesystem discovery, default-deny capability grants, two-phase installer, `/plugins` dashboard tab, per-plugin observability, reference plugin (2026-05-27, tag `v0.5.0`).
- v0.6 Contribution Gate (phases 51-59): substantially complete and rehearsal-ready. The single-atomic-commit gate flip (Phase 59) is drafted but not yet landed and is carried into v0.7 as a pending todo. No v0.6.0 tag yet.

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
| No PyPI publishing in v0.6 (Trusted Publishing PEP 807 deferred) | horus-os does not currently publish to PyPI. Standing up Trusted Publishing requires a PyPI project + maintainer setup outside the v0.6 contribution-gate scope. Decision documented in `.planning/decisions/no-pypi-in-v0.6.md`. | accepted (v0.6) |
| No Contributor License Agreement | Apache 2.0 inbound-equals-outbound on PR action is sufficient for a project of this scale. No CLA bot, no separate signing document. Decision in `.planning/decisions/no-cla.md`. | accepted (v0.6) |
| No `actions/stale` auto-close | Aging issues are real signal; auto-close creates a false "we are responsive" impression. Honest "may go silent up to 2 weeks" disclaimer in `docs/TRIAGE.md` instead. Decision in `.planning/decisions/no-stale-bot.md`. | accepted (v0.6) |
| Keyless OIDC signing via sigstore | Avoids long-lived GPG keys; every signature auditable in Rekor transparency log. Matches industry direction. Decision in `.planning/decisions/sigstore-keyless.md`. | accepted (v0.6) |
| CycloneDX 1.6 JSON SBOM format | cyclonedx-py environment has mature venv introspection; FRESH-venv-aligned SBOM. Decision in `.planning/decisions/sbom-cyclonedx.md`. | accepted (v0.6) |
| Optional cloud integrations (Supabase, Vercel, Tailscale, Discord, GitHub) | Adds remote command-center power without breaking the "runs locally, no required SaaS" core value. Every integration is opt-in and the system starts without any of them. | accepted (v0.7) |
| In-app key management gated on the localhost bind | The dashboard serves on 127.0.0.1 by default, so editing credentials from the local UI is trusted. Exposing /api remotely requires an auth layer first; the setup walkthroughs flag this. | accepted (v0.7) |

## Out of Scope (initial release)

- Hosted SaaS deployment.
- Mobile clients.
- Multi-tenant patterns.
- Kubernetes operators.
- Features that require any paid third-party account beyond user-supplied LLM API keys.
- Voice integrations (no current milestone).
- Hosted plugin marketplace / discovery catalog (post-v0.5; v0.5 uses Python entry points + local directory only).
- Sandboxed plugin execution via OS-level isolation (subprocess/container). v0.5 uses in-process loading with capability-declaration permission grants; OS isolation remains a post-v0.6 consideration if real-world abuse warrants it (deferred - v0.6 focuses on contribution-gate readiness instead).

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
2. Core Value check - still the right priority?
3. Audit Out of Scope - reasons still valid?
4. Update Context with current state

## Footer

*Last updated: 2026-06-02 - v0.7 Command Center complete and verified across all ten phases (60-68); the v0.7.0 release is staged locally and awaits owner go-ahead to publish. Phase 68 wired the three-OS hard gate (ubuntu/macos/windows x Python 3.11/3.12 with an .[all] install-smoke matrix, pinned by tests/test_ci_matrix_three_os.py, REL-16) and authored the v0.7.0 release notes (CHANGELOG [0.7.0], docs/MIGRATION-v0.5-to-v0.7.md, docs/RELEASE-NOTES-v0.7.0.md, REL-17). A standard-depth code review of the release prose caught and fixed two Critical doc defects (the schema range is v6 to v12 with five new tables, and the verification command is `SELECT version FROM schema_version` against horus.sqlite, not PRAGMA user_version) plus the Discord invite permission integer (292057869376, public threads). version 0.7.0, SCHEMA_VERSION 12, full suite green modulo the documented OTEL/release-gate baseline. The cross-OS CI green run, the owner-confirmed release publication (push, tag v0.7.0, gh release create, merge to main), and a full-strength release_gate re-run are carried in 68-HUMAN-UAT.md per the D-07 hard boundary. v0.6 Contribution Gate substantially complete with the gate flip pending.*
