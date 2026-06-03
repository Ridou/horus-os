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

## Architecture sketch

| Layer | Default choice | Notes |
|-------|----------------|-------|
| Agent runtime | Python + Anthropic SDK + Google Gemini SDK, plus an optional OpenAI-compatible local LLM provider | Synchronous and async paths both supported |
| Persistence | SQLite (WAL mode) | Single file; trivially portable |
| Vector store | On-device ONNX embeddings + sqlite-vec KNN (opt-in via `[local-memory]`) | Off by default; zero network egress on memory writes |
| Knowledge base | Local markdown files + keyword and optional vector search | Edit in any markdown editor, including Obsidian |
| Dashboard | Next.js, served locally, with a streaming chat surface and an agent store | Optional; CLI works without it |
| Chat surface | CLI and the dashboard chat, plus opt-in Discord, Slack, Email, Calendar, and Twilio voice adapters | |
| Process manager | Native OS service file (systemd unit, launchd plist, Windows NSSM service) | One reference recipe per OS |

This table reflects the choices made through v0.8. See `ARCHITECTURE.md` for the implemented shape and `ROADMAP.md` for what comes next.

## What this project is not

`horus-os` is intentionally not:

- A multi-user chat platform.
- A no-code agent builder.
- An IDE replacement.
- A general-purpose workflow engine.

The goal is a personal command center for one person, running locally, with full transparency over what the agents are doing.

## Status

Alpha, v0.8.0 (2026-06-02), "Local-first and Autonomous Research." See `CHANGELOG.md` and the [Releases page](https://github.com/Ridou/horus-os/releases) for the full history.
