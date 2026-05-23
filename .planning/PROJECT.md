# horus-os

An open-source, self-hosted autonomous AI command center.

## What This Is

A personal AI command center that runs on the user's own machine. Multiple AI agents take instructions through a chat surface (CLI or web), execute tasks against a local persistent knowledge base, and surface results in a local web dashboard. Cloud AI calls are explicit, billed to the user's own API keys, and never required for the system to start.

## Core Value

Run a personal team of AI agents on your laptop, with full transparency over every action, every memory write, and every credential used.

## Requirements

### Active

(Defined in REQUIREMENTS.md for v0.1)

### Validated

(none yet, pre-alpha)

## Current Milestone: v0.1 Foundation

**Goal:** Ship the smallest standalone system a stranger can clone, configure with their own API keys, and use through either a CLI or a local web chat. One agent. One tool. One persistent memory layer.

**Decisions locked in for v0.1:**
- CLI and web chat both shipped at v0.1, in parallel
- Anthropic and Google Gemini both as default LLM providers (direct SDKs, no abstraction layer)
- Setup wizard provides direct links to provider consoles plus click-to-paste API key flow
- Apache 2.0 license
- Three-OS hard gate before public release (macOS, Ubuntu 22.04, Windows 11)

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
| Anthropic + Gemini, no abstraction layer | Both providers have first-class support in the maintainer's existing setups. An abstraction layer adds debt before the first user. | accepted (v0.1) |
| CLI and web chat parallel at v0.1 | Different users prefer different surfaces. Both share the same backend so the marginal cost is the second UI shell, not a second runtime. | accepted (v0.1) |
| SQLite over Postgres for default | Single file, zero ops, trivially portable, ships with the binary. Postgres is an option later for users who want it. | accepted (v0.1) |
| Apache 2.0 license | Permissive, patent-grant clause important for AI tooling. Compatible with most third-party libraries we will use. | accepted (v0.1) |
| No private sibling reference | This project is built from scratch as public-from-day-one. No code or planning is imported from any private project. | accepted (permanent) |

## Out of Scope (initial release)

- Hosted SaaS deployment.
- Mobile clients.
- Multi-tenant patterns.
- Kubernetes operators.
- Features that require any paid third-party account beyond user-supplied LLM API keys.
- Voice integrations (deferred to v0.3+).
- Discord, Slack, or other chat-platform adapters (deferred to v0.3 adapter ecosystem).
