# horus-os

An open-source, self-hosted autonomous AI command center.

## What This Is

A personal AI command center that runs on the user's own machine. Multiple AI agents take instructions through a chat surface (CLI or web), execute tasks against a local persistent knowledge base, and surface results in a local web dashboard. Cloud AI calls are explicit, billed to the user's own API keys, and never required for the system to start.

## Core Value

Run a personal team of AI agents on your laptop, with full transparency over every action, every memory write, and every credential used.

## Requirements

### Active

Defined in REQUIREMENTS.md under `## v0.6 Contribution Gate` (SIGN, SUPPLY, CIHARD, CONTRIB, SECDISC, plus continuation TEST/REL categories).

### Validated

- v0.1 Foundation: CORE, AGENT, TOOL, MEM, DASH, WIZARD, TEST-01..03, REL-01..02 (shipped 2026-05-23, tag `v0.1.0`).
- v0.2 Multi-Agent + Streaming: MA, STREAM, ADAPT, MIG, TEST-04..06, REL-03..04 (shipped 2026-05-23, tag `v0.2.0`).
- v0.3 Adapter Ecosystem: ART, DISC, SLAK, MAIL, CAL, DASH-3, TEST-07..10, REL-05..06 (shipped 2026-05-24, tag `v0.3.0`).
- v0.4 Observability: METRIC, STORE, PRICE, DASH-4, USAGE, OTEL, BASELINE, TEST-11..15, REL-07..09, MIG-04 (shipped 2026-05-26, tag `v0.4.0`).
- v0.5 Plugin System: PLUG, MANIFEST, ISOLATE, INSTALL, PERMISSION, DASH-5, REFERENCE, TEST-16..21, REL-10..12, MIG-05 (shipped 2026-05-27, tag `v0.5.0`).

## Current Milestone: v0.6 Contribution Gate

**Goal:** Flip horus-os from solo-development mode to "outside contributions welcome" by landing the trust, supply-chain, and contributor-experience infrastructure required to safely accept fork PRs, then flipping the public gate at v0.6.0 ship.

**Target features:**
- CI signing and signed releases — sigstore/cosign on built artifacts (wheel + sdist), signed git tags, signed GitHub Releases.
- Supply-chain checks — SBOM generation at release time, pip-audit + safety scans on every PR (both base and `[dev,otel]` extras), Dependabot for runtime and dev deps.
- Fork-PR CI hardening — secrets restricted to in-repo PRs, maintainer-label gating for full CI on fork PRs (`safe-to-test` style), pinned action versions by SHA.
- Contributor docs and templates — CONTRIBUTING.md expansion (claim flow, branch policy, commit format, test/doc expectations), PR template with checklist (tests, docs, changelog, license header), issue templates (bug, feature, security advisory), CODEOWNERS, triage SLA doc.
- SECURITY.md and vulnerability disclosure — private disclosure channel, response SLO, public advisory flow with CVE coordination notes.
- Release-gate extension — new checks (signature present on artifacts, SBOM attached, pip-audit clean) refuse an unsigned, un-SBOMed, or vulnerable tag.
- Three-OS hard gate (default for every milestone).
- Gate flip — STATUS.md TL;DR rewritten ("contributions OPEN"), README CTAs land, first-PR-window opens at v0.6.0 ship.

**Decisions to confirm during planning:**
- Signing identity: GitHub OIDC via sigstore (keyless) preferred over long-lived maintainer keys; lock at requirements time.
- SBOM format: CycloneDX vs SPDX. Likely CycloneDX (Python tooling more mature). Lock at requirements time.
- Supply-chain scanner: pip-audit (PyPA, vulnerability DB) confirmed; safety as optional second opinion. Lock at requirements time.
- Fork-PR gating mechanism: GitHub Actions `pull_request_target` boundary vs maintainer-label trigger. Lock at requirements time.
- Anti-goal still in force: no paid third-party account required for any check.
- Apache 2.0 license (unchanged).
- Three-OS hard gate before release (macOS, Ubuntu, Windows), Python 3.11 + 3.12.

**Shipped:**
- v0.1 Foundation — CLI + web chat, Anthropic + Gemini, one agent, six tools, memory layer (2026-05-23, tag `v0.1.0`).
- v0.2 Multi-Agent + Streaming — named agent profiles, `delegate_to_agent`, provider streaming, adapter plugin contract (2026-05-23, tag `v0.2.0`).
- v0.3 Adapter Ecosystem — lifecycle hooks, Discord/Slack/Email/Calendar adapters, AdapterRegistry, dashboard Adapters tab (2026-05-24, tag `v0.3.0`).
- v0.4 Observability — ObservationBus, SQLite cost/latency/reliability persistence, bundled pricing.json, `/observability` dashboard tab, `horus-os usage` CLI, opt-in OTel adapter behind `[otel]` extra (2026-05-26, tag `v0.4.0`).
- v0.5 Plugin System — TOML manifest contract, entry-point + filesystem discovery, default-deny capability grants, two-phase installer, `/plugins` dashboard tab, per-plugin observability, reference plugin (2026-05-27, tag `v0.5.0`).

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
- Sandboxed plugin execution via OS-level isolation (subprocess/container). v0.5 uses in-process loading with capability-declaration permission grants; OS isolation remains a post-v0.6 consideration if real-world abuse warrants it (deferred — v0.6 focuses on contribution-gate readiness instead).

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

*Last updated: 2026-05-29 - milestone v0.6 Contribution Gate started; v0.5 Plugin System shipped as v0.5.0 on 2026-05-27.*
