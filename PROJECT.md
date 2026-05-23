# horus-os

An open-source, self-hosted autonomous AI command center.

## Project intent

`horus-os` lets a single person run a personal team of AI agents from one workstation. Agents take instructions over a chat surface, execute tasks against a persistent knowledge base, and surface results in a web dashboard. The whole stack runs on the user's own hardware. Cloud AI calls are explicit, billed to the user's own API keys, and never required for the system to start.

## Core values

1. **Run on your machine.** Default deployment is a single laptop or home server. No vendor lock-in. No required SaaS dependency for core operation.
2. **Bring your own keys.** AI providers, search providers, calendar/email integrations, and storage backends are configured through environment variables. The user owns every credential.
3. **Inspect everything.** Every agent action writes a trace. Every memory write is reviewable. There are no opaque "magic" subsystems.
4. **Small surface, growable.** Ship a minimum viable agent runtime first. Extension points are explicit: agents, tools, integrations, dashboard panels.

## Out of scope (initial release)

- Hosted SaaS offering.
- Mobile clients.
- Multi-tenant deployment patterns.
- Production-scale Kubernetes operators.
- Any feature that requires a paid third-party account beyond optional AI API keys.

## Architecture sketch (subject to revision)

| Layer | Default choice | Notes |
|-------|----------------|-------|
| Agent runtime | Python + Anthropic SDK + Google Gemini SDK | Synchronous and async paths both supported |
| Persistence | SQLite (WAL mode) | Single file; trivially portable |
| Vector store | Local Chroma or duckdb-vss | Embedding backend pluggable |
| Knowledge base | Local markdown files + indexed search | User edits in any editor |
| Dashboard | Next.js, served locally | Optional; CLI works without it |
| Chat surface | CLI first; web chat next; third-party (Discord, Slack) via opt-in adapters | |
| Process manager | Native OS service file (systemd unit, launchd plist, Windows scheduled task) | One reference recipe per OS |

This table is a starting point. The first phase decides which of these to actually pick for v0.1.

## What this project is not

`horus-os` is intentionally not:

- A multi-user chat platform.
- A no-code agent builder.
- An IDE replacement.
- A general-purpose workflow engine.

The goal is a personal command center for one person, running locally, with full transparency over what the agents are doing.

## Status

Pre-alpha. No releases. No public repo yet.
