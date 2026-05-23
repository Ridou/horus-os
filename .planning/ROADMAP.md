# Roadmap

## Milestones

- [x] **v0.1 Foundation** (Phases 01-11), shipped 2026-05-23 as v0.1.0. CLI + web chat, Anthropic + Gemini, one agent, six tools, full memory layer, 3-OS install gate, first public release.

## Phases

### v0.1 Foundation (Phases 01-11)

**Milestone Goal:** Ship the smallest standalone system a stranger can clone, configure with their own API keys, and use through either a CLI or a local web chat. One agent. One tool. One persistent memory layer. Two LLM providers (Anthropic, Google Gemini) wired in directly.

**Parallelization:** 01 → 02 → (03, 04) → (05, 06) → 07 ∥ 08 → 09 → 10 → 11. Most strict-sequential; chat surfaces 07 (CLI) and 08 (web) can run in parallel after the memory layer lands.

- [x] **Phase 01: Repo scaffold and CI**, pyproject.toml, src layout, ruff + pytest, GitHub Actions running lint and test on Ubuntu, macOS, Windows. (completed 2026-05-23)
- [x] **Phase 02: Agent runtime core**, Python module that takes a prompt, invokes Anthropic or Gemini with one tool, returns a structured result. Sync and async paths both supported. (completed 2026-05-23)
- [x] **Phase 03: Persistence layer**, SQLite schema for tasks, traces, agent state. Migrations are idempotent. WAL mode. (completed 2026-05-23)
- [x] **Phase 04: Tool registry**, Register a callable as a tool, expose it to the agent, log every invocation. First example tool: read a local file. (completed 2026-05-23)
- [x] **Phase 05: Memory layer, read path**, Agent searches a markdown notes folder and reads files. (completed 2026-05-23)
- [x] **Phase 06: Memory layer, write path**, Agent appends to the notes folder with a structured trail. Every write is reviewable. (completed 2026-05-23)
- [x] **Phase 07: CLI surface**, `horus-os run "<prompt>"` runs an agent against the local stack. Output is structured. Also: `init`, `serve` (stub), `traces`. Multi-turn tool-execution loop shipped. (completed 2026-05-23)
- [x] **Phase 08: Web chat and dashboard**, single-page HTML dashboard served locally by FastAPI. Hosts a chat surface, traces explorer, and writes audit view. (completed 2026-05-23; Next.js deferred to a v0.x evolution if richer UX is needed)
- [x] **Phase 09: Setup wizard with API key onboarding**, `horus-os init --interactive` walks a new user through configuration. Direct links to Anthropic console and Google AI Studio. Validates keys with a live ping before saving. Idempotent and resumable. (completed 2026-05-23)
- [x] **Phase 10: Three-OS install verification**, Fresh-VM install on macOS, Ubuntu, Windows via the install-smoke CI job. (completed 2026-05-23)
- [x] **Phase 11: First public release**, Tagged v0.1.0 on origin, CHANGELOG written, version bumped. (completed 2026-05-23)

## Progress

- Total phases: 11
- Completed phases: 11
- Total plans: 13
- Completed plans: 13
- Percent: 100
- Milestone v0.1 Foundation: SHIPPED as v0.1.0 on 2026-05-23
