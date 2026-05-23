# Roadmap

## Current milestone: v0.1 Foundation

**Goal:** Ship the smallest standalone system a stranger can clone, configure with their own API keys, and use through either a CLI or a local web chat. One agent. One tool. One persistent memory layer. Two LLM providers (Anthropic, Google Gemini) wired in directly.

### Decisions locked in for v0.1

| Decision | Choice |
|----------|--------|
| Chat surfaces | CLI and web chat both shipped at v0.1, in parallel |
| LLM providers | Anthropic and Google Gemini both, direct SDKs, no abstraction layer |
| API key onboarding | Setup wizard provides direct links to the provider consoles plus a click-to-paste flow so users can be configured in under five minutes |
| Runtime target | macOS, Ubuntu 22.04, Windows 11 (three-OS hard gate before public release) |
| License | Apache 2.0 |

### Phases

| # | Title | Goal | Status |
|---|-------|------|--------|
| 01 | Repo scaffold and CI | pyproject.toml, src layout, ruff + pytest, GitHub Actions running lint and test on Ubuntu, macOS, Windows | shipped 2026-05-23 |
| 02 | Agent runtime core | Python module that takes a prompt, invokes Anthropic or Gemini with one tool, returns a structured result. Sync and async paths both supported. | shipped 2026-05-23 |
| 03 | Persistence layer | SQLite schema for tasks, traces, agent state. Migrations are idempotent. WAL mode. | shipped 2026-05-23 |
| 04 | Tool registry | Register a callable as a tool, expose it to the agent, log every invocation. First example tool: read a local file. | shipped 2026-05-23 |
| 05 | Memory layer, read path | Agent searches a markdown notes folder and reads files. No writes yet. | shipped 2026-05-23 |
| 06 | Memory layer, write path | Agent appends to the notes folder with a structured trail. Every write is reviewable. | shipped 2026-05-23 |
| 07 | CLI surface | `horus-os run "<prompt>"` runs an agent against the local stack. Output is structured. Also: `init`, `serve`, `traces`. | 07-00 shipped, 07-01 pending |
| 08 | Web chat and dashboard | Next.js app served locally. Hosts a chat surface and a traces explorer. Reads from the same SQLite the CLI uses. | planning |
| 09 | Setup wizard with API key onboarding | `horus-os init` walks a new user through configuration. Direct links to Anthropic console and Google AI Studio. Validates keys with a live ping before saving. Idempotent and resumable. | planning |
| 10 | Three-OS install verification | Fresh-VM install on macOS, Ubuntu 22.04, Windows 11. Same exit codes, same first-run experience. | planning |
| 11 | First public release | Tag v0.1.0, write release notes, publish the public repo. | planning |

## Future milestones (working list, not committed)

- **v0.2 Multi-agent.** Named agents, routing, cross-agent handoff.
- **v0.3 Adapter ecosystem.** Discord, Slack, calendar, email as opt-in integrations.
- **v0.4 Observability.** Cost tracking per agent, per tool. Dashboards.
- **v0.5 Plugin system.** Third-party tools and agents load from a manifest.

These are placeholders. Shape is decided in flight.

## Anti-goals

- Coupling to any single cloud provider beyond optional LLM API choice.
- Shipping features that require any paid account besides the user's LLM API key.
- Multi-tenant deployment patterns.
- A hosted SaaS offering of horus-os.
