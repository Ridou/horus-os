# Roadmap

## Milestones

- [ ] **v0.1 Foundation** (Phases 01-11), CLI + web chat, Anthropic + Gemini, one agent, one tool, one memory layer, 3-OS install gate, first public release

## Phases

### v0.1 Foundation (Phases 01-11)

**Milestone Goal:** Ship the smallest standalone system a stranger can clone, configure with their own API keys, and use through either a CLI or a local web chat. One agent. One tool. One persistent memory layer. Two LLM providers (Anthropic, Google Gemini) wired in directly.

**Parallelization:** 01 → 02 → (03, 04) → (05, 06) → 07 ∥ 08 → 09 → 10 → 11. Most strict-sequential; chat surfaces 07 (CLI) and 08 (web) can run in parallel after the memory layer lands.

- [x] **Phase 01: Repo scaffold and CI**, pyproject.toml, src layout, ruff + pytest, GitHub Actions running lint and test on Ubuntu, macOS, Windows. (completed 2026-05-23)
- [x] **Phase 02: Agent runtime core**, Python module that takes a prompt, invokes Anthropic or Gemini with one tool, returns a structured result. Sync and async paths both supported. (completed 2026-05-23)
- [ ] **Phase 03: Persistence layer**, SQLite schema for tasks, traces, agent state. Migrations are idempotent. WAL mode.
- [ ] **Phase 04: Tool registry**, Register a callable as a tool, expose it to the agent, log every invocation. First example tool: read a local file.
- [ ] **Phase 05: Memory layer, read path**, Agent searches a markdown notes folder and reads files.
- [ ] **Phase 06: Memory layer, write path**, Agent appends to the notes folder with a structured trail. Every write is reviewable.
- [ ] **Phase 07: CLI surface**, `horus-os run "<prompt>"` runs an agent against the local stack. Output is structured. Also: `init`, `serve`, `traces`.
- [ ] **Phase 08: Web chat and dashboard**, Next.js app served locally. Hosts a chat surface and a traces explorer.
- [ ] **Phase 09: Setup wizard with API key onboarding**, `horus-os init` walks a new user through configuration. Direct links to Anthropic console and Google AI Studio. Validates keys with a live ping before saving. Idempotent and resumable.
- [ ] **Phase 10: Three-OS install verification**, Fresh-VM install on macOS, Ubuntu 22.04, Windows 11.
- [ ] **Phase 11: First public release**, Tag v0.1.0, write release notes, publish the public repo.

## Progress

- Total phases: 11
- Completed phases: 2
- Total plans: 2
- Completed plans: 2
- Percent: 18
