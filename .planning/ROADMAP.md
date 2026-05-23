# Roadmap

## Milestones

- [x] **v0.1 Foundation** (Phases 01-11), shipped 2026-05-23 as v0.1.0. CLI + web chat, Anthropic + Gemini, one agent, six tools, full memory layer, 3-OS install gate, first public release.
- [ ] **v0.2 Multi-Agent + Streaming** (Phases 12-21), active. Named agent profiles, coordinator-to-sub-agent delegation, provider streaming on both CLI and dashboard, adapter plugin interface.

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

### v0.2 Multi-Agent + Streaming (Phases 12-21)

**Milestone Goal:** Move from "one agent answers questions" to "a personal team of agents that can hand off to each other, with live streaming responses in the CLI and dashboard." Named agent profiles persist in SQLite. A coordinator delegates to sub-agents. Both providers stream incremental tokens. The adapter plugin interface opens the door to external surfaces (Discord, Slack, webhook receivers) which arrive in v0.3.

**Parallelization:** 12 → 13 → (14 ∥ 15 ∥ 16 ∥ 17) → 18 → 19 → 20 → 21. Phase 12 (agent profile schema + migration) gates everything because it changes the storage layer. After 13 (runtime support for delegation) lands, surfaces and adapters can ship in parallel.

- [ ] **Phase 12: Agent profile model and schema migration**, `agent_profiles` table with name, system prompt, default model, allowed tools, memory scope. Idempotent forward migration from v0.1 schema. CRUD API. At least one default agent auto-created on `init`.
- [ ] **Phase 13: Multi-agent orchestration runtime**, `delegate_to_agent` tool. Parent and child trace linkage. A coordinator can invoke one or more sub-agents synchronously or in parallel. Iteration bound applies to the whole tree.
- [ ] **Phase 14: Streaming response support**, `run_agent_stream` async generator. Anthropic and Gemini streaming SDK paths. `run_agent` and `run_agent_loop` continue to work unchanged for non-streaming callers.
- [ ] **Phase 15: CLI multi-agent surface**, `horus-os agents` subcommand (list, show, create, edit, delete). `horus-os run --agent <name>`. Streaming output to terminal by default; `--no-stream` falls back to the v0.1 behavior.
- [ ] **Phase 16: Dashboard multi-agent view and streaming chat**, agents list, per-agent activity, delegate-tree visualization per run, live token streaming in the chat surface.
- [ ] **Phase 17: Adapter plugin interface**, Plugin contract via `importlib.metadata.entry_points("horus_os.adapters")`. One reference adapter ships: HTTP webhook receiver. Third-party adapters can register without forking horus-os.
- [ ] **Phase 18: Documentation and examples refresh**, Update ARCHITECTURE.md for the multi-agent shape. Add `examples/multi_agent.py`, `examples/streaming.py`, `examples/custom_adapter.py`. Document the migration path for v0.1 users.
- [ ] **Phase 19: Test surface expansion**, End-to-end multi-agent flows, streaming partial-failure modes, adapter contract tests. Cross-OS coverage maintained.
- [ ] **Phase 20: Three-OS install verification (v0.2)**, Same hard gate as Phase 10, re-targeted at the v0.2 feature set. Fresh-VM install on macOS, Ubuntu, Windows passes through `install-smoke`.
- [ ] **Phase 21: v0.2.0 release**, Tag v0.2.0 on origin, CHANGELOG updated, version bumped, GitHub Release published with migration notes.

## Progress

- Total phases: 21
- Completed phases: 11 (v0.1)
- Active milestone: v0.2 Multi-Agent + Streaming (0/10 phases)
- Total plans (v0.1): 13
- Completed plans (v0.1): 13
- Percent complete (overall): 52%
- Last shipped: v0.1.0 on 2026-05-23
