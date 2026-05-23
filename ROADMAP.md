# Roadmap

## Current milestone: v0.1 Foundation

**Goal:** Ship the smallest standalone system a stranger can clone, install, and use. One agent. One tool. One persistent memory layer. One way to talk to it.

### Phases (sketch, refined per phase)

| # | Title | Goal | Status |
|---|-------|------|--------|
| 01 | Repo scaffold and CI | Apache 2.0 license, contributing guide, code of conduct, lint and test CI on three OSes (macOS, Ubuntu, Windows) | planning |
| 02 | Agent runtime core | A Python module that takes a prompt, invokes an LLM with one tool, returns a result. Synchronous. No network besides the LLM call. | planning |
| 03 | Persistence layer | SQLite schema for tasks, traces, agent state. Migrations are idempotent. | planning |
| 04 | Tool registry | A way to register a callable as a tool, expose it to the agent, and log every invocation. One example tool: read a local file. | planning |
| 05 | Memory layer (read) | A markdown notes folder the agent can search and read. No writes yet. | planning |
| 06 | Memory layer (write) | Agent can append to a notes folder with a structured trail. Every write is reviewable. | planning |
| 07 | CLI surface | `horus-os run "<prompt>"` runs an agent against the local stack. Output is structured. | planning |
| 08 | Dashboard skeleton | Next.js app that lists recent traces, lets the user inspect any agent run. Read-only. | planning |
| 09 | Setup wizard | `horus-os init` walks a new user through configuration, validates external keys, writes a starter `.env`. Idempotent and resumable. | planning |
| 10 | Three-OS install verification | Fresh-VM install on macOS, Ubuntu 22.04, Windows 11. Same exit codes, same first-run experience. | planning |
| 11 | First public release | Tag v0.1.0, write a release post, publish a public repo. | planning |

## Future milestones (working list, not committed)

- **v0.2 Multi-agent.** More than one named agent; routing decisions; cross-agent handoff.
- **v0.3 Web chat surface.** Lightweight in-browser chat for the local instance.
- **v0.4 Adapter ecosystem.** Discord, Slack, calendar, email as opt-in integrations.
- **v0.5 Observability.** Cost tracking per agent, per tool. Dashboards.
- **v0.6 Plugin system.** Third-party tools and agents load from a manifest.

These are placeholders. The shape is decided in flight.

## Anti-goals

- Building an extraction pipeline for any private codebase.
- Coupling to any vendor or specific cloud.
- Shipping features that depend on the maintainer's personal stack.
